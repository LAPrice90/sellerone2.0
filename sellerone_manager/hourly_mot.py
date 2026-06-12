from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .b_order_recovery import (
    MARKETPLACE_PLAN_CSV_NAME as B_ORDER_RECOVERY_PLAN_CSV_NAME,
    RECOVERY_DIR_NAME as B_ORDER_RECOVERY_DIR_NAME,
    SUMMARY_CSV_NAME as B_ORDER_RECOVERY_SUMMARY_CSV_NAME,
    build_b_order_recovery_plan,
    write_b_order_recovery_outputs,
)
from .b_order_promotion import (
    MANIFEST_JSON_NAME as B_ORDER_PROMOTION_MANIFEST_JSON_NAME,
    PREVIEW_CSV_NAME as B_ORDER_PROMOTION_PREVIEW_CSV_NAME,
    PROMOTION_DIR_NAME as B_ORDER_PROMOTION_DIR_NAME,
    build_b_order_promotion_plan,
)
from .b_marketplace_coverage import (
    COVERAGE_CSV_NAME as B_MARKETPLACE_COVERAGE_CSV_NAME,
    COVERAGE_DIR_NAME as B_MARKETPLACE_COVERAGE_DIR_NAME,
    SUMMARY_CSV_NAME as B_MARKETPLACE_SUMMARY_CSV_NAME,
    build_b_marketplace_coverage_report,
    write_b_marketplace_coverage_outputs,
)
from .b_stock_receipt_intake_preview import (
    OUTPUT_DIR_NAME as B_STOCK_RECEIPT_SYNC_DIR_NAME,
    SUMMARY_CSV_NAME as B_STOCK_RECEIPT_SYNC_SUMMARY_CSV_NAME,
)
from .autonomy_policy import controlled_technical_pause_allowed, quiet_autonomy_active
from .paths import get_manager_paths
from .sellerboard_bridge import (
    ORDER_RECONCILIATION_COLUMNS,
    ORDER_RECONCILIATION_NAME,
    SKU_GAP_COLUMNS,
    SKU_GAP_NAME,
    SUMMARY_COLUMNS,
    SUMMARY_NAME,
)
from .sellerboard_email_intake import (
    EMAIL_INTAKE_DIR_NAME as SELLERBOARD_EMAIL_INTAKE_DIR_NAME,
    SUMMARY_CSV_NAME as SELLERBOARD_EMAIL_INTAKE_SUMMARY_CSV_NAME,
    build_sellerboard_email_intake_report,
)
from .schemas import HOURLY_MOT_COLUMNS, MOT_RETEST_QUEUE_COLUMNS, MOT_WORKLIST_COLUMNS


A_DAILY_WARN_HOURS = 26.0
A_DAILY_FAIL_HOURS = 36.0
A_LOCK_FAIL_HOURS = 6.0
B_MANIFEST_WARN_HOURS = 3.0
B_MANIFEST_FAIL_HOURS = 6.0
B_HEARTBEAT_WARN_SECONDS = 300.0
B_HEARTBEAT_FAIL_SECONDS = 900.0
E_DAILY_WARN_HOURS = 26.0
E_DAILY_FAIL_HOURS = 36.0
E_LOCK_WARN_SECONDS = 900.0
E_LOCK_FAIL_SECONDS = 21600.0
H_MANIFEST_WARN_HOURS = 3.0
H_HEARTBEAT_WARN_SECONDS = 900.0
H_HEARTBEAT_FAIL_SECONDS = 1800.0
F_LIVE_WARN_HOURS = 3.0
F_LIVE_FAIL_HOURS = 6.0
F_MANAGER_WARN_HOURS = 3.0
F_MANAGER_FAIL_HOURS = 6.0
F_TEST_MODE_WARN_HOURS = 168.0
F_TEST_MODE_FAIL_HOURS = 336.0
F_REVIEW_WARN_HOURS = 168.0
F_REVIEW_FAIL_HOURS = 336.0
F_CHILD_WARN_SECONDS = 900.0
F_CHILD_FAIL_SECONDS = 1800.0
F_GMAIL_SOURCE_WARN_HOURS = 168.0
F_GMAIL_SOURCE_FAIL_HOURS = 336.0
F_PROGRESS_STALL_MIN_CHUNKS = 5
F_PROGRESS_STALL_MIN_MINUTES = 20.0
F_PROGRESS_STALL_MAX_PENDING_DROP = 1
O_PROOF_WARN_HOURS = 168.0
O_PROOF_FAIL_HOURS = 336.0
MOT_ACTIVE_WORK_STATUSES = {"new", "assigned", "in_progress", "fixed_needs_retest", "retest_failed", "blocked_needs_luke"}
MOT_TERMINAL_WORK_STATUSES = {"proved", "parked"}
MOT_WARN_WORK_CHECKS = {
    "b_fallback_cost_proof_reconciliation",
    "b_fallback_token_cost_audit",
    "b_management_ready_for_maintenance",
    "b_marketplace_coverage_report",
    "b_level3_fee_shipping_api_proof_map",
    "b_order_truth_completion",
    "b_pnl_daily",
    "b_refund_fee_shipping_gap_review",
    "b_refund_return_token_bridge",
    "b_sellerboard_refund_fee_roi_bridge",
    "b_stock_receipt_token_sync",
    "h_token_floor_source_guard",
    "o_user_working_readiness",
    "o_h_maintenance_controller_gate",
    "o_h_market_proof_gate",
}
MOT_SUMMARY_ONLY_CHECKS = {
    ("H", "h_manager_readiness"),
}

A_FORBIDDEN_ACTIONS = (
    "no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; "
    "no local DB alignment; no downstream output masking; no scope widening"
)
B_FORBIDDEN_ACTIONS = (
    "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; "
    "no price or queue changes; no token/data correction; no local DB alignment; "
    "no output deletion; no scope widening"
)
E_FORBIDDEN_ACTIONS = (
    "no E worker run; no live worker cycle; no publish enablement; no legacy Sheet write; "
    "no price changes; no queue edits; no local DB alignment; no output deletion; "
    "no worker restart; no scope widening"
)
H_FORBIDDEN_ACTIONS = (
    "no H run; no scheduler ownership changes; no publish; no price changes; "
    "no queue edits; no Google Sheets writes; no local DB alignment; "
    "no output deletion; no worker restart; no scope widening"
)
F_FORBIDDEN_ACTIONS = (
    "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; "
    "no worker restart; no Google Sheets writes; no price changes; no local DB alignment; "
    "no output deletion; no scanner repair; no scope widening"
)
O_FORBIDDEN_ACTIONS = (
    "no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; "
    "no price change; no queue edit; no local DB alignment; no output deletion; no business decision; "
    "no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; "
    "no scope widening"
)
O_USER_WORKING_REQUIRED_CHECKS = (
    "o_mid_build_stage_map",
    "o_active_restock_proof_files",
    "o_downstream_contract_files",
    "o_restock_session_readiness",
    "o_restock_supplier_batch_drafts",
    "o_supplier_file_source_index",
    "o_supplier_file_presence_probe",
    "o_supplier_file_evidence_visibility",
    "o_supplier_file_proof_coverage_map",
    "o_supplier_proof_work_queue",
    "o_supplier_proof_queue_filter",
    "o_supplier_proof_action_workbench",
    "o_supplier_proof_field_focus_filter",
    "o_purchase_approval_preview",
    "o_purchase_approval_guardrails",
    "o_po_draft_readiness_preview",
    "o_po_line_design_preview",
    "o_po_draft_packet_review",
    "o_po_draft_hold_review",
    "o_po_draft_file_shape_preview",
    "o_po_preview_construction_summary",
    "o_po_draft_review_controls",
    "o_po_draft_export_preview",
    "o_po_draft_export_gate",
    "o_real_po_readiness_gate",
    "o_real_po_gate_clearance_worklist",
    "o_real_po_supplier_gate_clearance",
    "o_buy_ready_guardrails",
    "o_legacy_bridge_source_labels",
    "o_po_draft_source_separation",
    "o_receiving_send_safety",
    "o_completion_claim_guard",
)
O_USER_WORKING_REQUIRED_WARN_OK_CHECKS = {
    "o_active_restock_proof_files",
}
O_USER_WORKING_TOLERATED_WARN_CHECKS = {
    "o_inbound_fba_cost_allocation_proof",
    "o_profit_input_blocker_breakdown",
    "o_inbound_fba_source_options",
    "o_h_maintenance_controller_gate",
    "o_h_market_proof_gate",
}
O_USER_WORKING_UI_FILES = (
    "scripts/flows/O/O400_operator_ui.py",
    "scripts/flows/O/O410_product_database_ui.py",
    "scripts/flows/O/O420_product_database_edit_ui.py",
)
MOT_FORBIDDEN_ACTIONS = {
    "A": A_FORBIDDEN_ACTIONS,
    "B": B_FORBIDDEN_ACTIONS,
    "E": E_FORBIDDEN_ACTIONS,
    "H": H_FORBIDDEN_ACTIONS,
    "F": F_FORBIDDEN_ACTIONS,
    "O": O_FORBIDDEN_ACTIONS,
}
SUPPORTED_MOT_FLOWS = ("A", "B", "E", "H", "F", "O")
F_DEFAULT_GMAIL_LABEL_BY_SUPPLIER = {
    "abgee": "ABGee",
    "td_synnex": "TD Synnex",
    "tropicana_wholesale": "Tropicana",
}

A_REQUIRED_OUTPUTS = [
    {
        "check": "a001_listings_latest",
        "producer": "A001_run_listings_to_sheet.py",
        "path": "out/merchant_listings_latest.csv",
        "summary": "Amazon live listings snapshot exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A001 local refresh code only; legacy Sheet writing must stay disabled unless Luke approves it.",
    },
    {
        "check": "a002_catalog_items",
        "producer": "A002_run_catalog_items_to_sheet.py",
        "path": "out/catalog_items_flat.csv",
        "summary": "Amazon catalog item detail snapshot exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A002 local refresh code only; legacy Sheet writing must stay disabled unless Luke approves it.",
    },
    {
        "check": "a003_inventory_summaries",
        "producer": "A003_run_inventory_to_sheet.py",
        "path": "out/inventory_summaries.csv",
        "summary": "Amazon stock summary exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A003 inventory proof only; no stock correction or database alignment without a separate approved task.",
    },
    {
        "check": "a003_inventory_history",
        "producer": "A003_run_inventory_to_sheet.py",
        "path": "out/inventory_history.csv",
        "summary": "Inventory history exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A003 inventory proof only; no stock correction or database alignment without a separate approved task.",
    },
    {
        "check": "a003_inventory_snapshot_latest",
        "producer": "A003_run_inventory_to_sheet.py",
        "path": "out/inventory_snapshot_latest.csv",
        "summary": "Latest inventory snapshot exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A003 inventory proof only; no stock correction or database alignment without a separate approved task.",
    },
    {
        "check": "a004_fees_latest",
        "producer": "A004_run_fees_to_sheet.py",
        "path": "out/fees_latest.csv",
        "summary": "Amazon fee estimate output exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A004 local fee refresh code only; legacy Sheet writing must stay disabled unless Luke approves it.",
    },
    {
        "check": "a016_daily_intel",
        "producer": "A016_refresh_phase1_daily_intel.py",
        "path": "out/phase1_daily_intel_latest.csv",
        "summary": "Daily pricing-support intelligence exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A016 daily-intel proof only; no H repricing changes in this boundary.",
    },
    {
        "check": "a015_a_checklist",
        "producer": "A015_build_system_health_check.py",
        "path": "out/cycle_alerts/checklist_A.csv",
        "summary": "A-owned health checklist exists and is fresh.",
        "min_rows": 1,
        "safe_repair_boundary": "A015 A-profile proof only; do not use A015 alone as full A-cycle proof.",
    },
]

A_PROOF_ONLY_OUTPUTS = [
    {
        "check": "a018_phase1_floor_table",
        "producer": "A018_build_phase1_floor_table.py",
        "path": "out/phase1_floor_table_latest.csv",
        "summary": "Phase1 floor table proof exists for downstream H support.",
        "min_rows": 1,
        "safe_repair_boundary": "A018 proof mapping only; do not add A018 to A run order or change floor values in this batch.",
    },
]

A_SQL_TABLES = [
    ("a003_sql_inventory_summaries", "a_inventory_summaries"),
    ("a003_sql_inventory_history", "a_inventory_history"),
    ("a003_sql_inventory_snapshot_latest", "a_inventory_snapshot_latest"),
    ("a004_sql_fees_latest", "a_fees_latest"),
    ("a016_sql_daily_intel", "a_phase1_daily_intel_latest"),
]

A_PROOF_ONLY_SQL_TABLES = [
    ("a018_sql_phase1_floor_table", "a_phase1_floor_table_latest"),
]

B_REQUIRED_OUTPUTS = [
    {
        "check": "b_orders_all",
        "producer": "B001_run_orders_to_sheet.py",
        "path": "out/orders_all.csv",
        "summary": "B order collection output exists, has rows, and is fresh.",
        "min_rows": 1,
        "warn_hours": 0.75,
        "fail_hours": 3.0,
        "safe_repair_boundary": "B order proof only; do not run B, edit orders, or write Sheets from MOT.",
    },
    {
        "check": "b_order_items_all",
        "producer": "B001_run_orders_to_sheet.py",
        "path": "out/order_items_all.csv",
        "summary": "B order-item output exists, has rows, and is fresh.",
        "min_rows": 1,
        "warn_hours": 0.75,
        "fail_hours": 3.0,
        "safe_repair_boundary": "B order-item proof only; do not run B, edit orders, or write Sheets from MOT.",
    },
    {
        "check": "b_order_master",
        "producer": "B004_build_order_master.py",
        "path": "out/order_master.csv",
        "summary": "B order master exists, has rows, and is fresh.",
        "min_rows": 1,
        "warn_hours": 1.0,
        "fail_hours": 3.0,
        "safe_repair_boundary": "B order-master proof only; no local DB alignment or downstream masking.",
    },
    {
        "check": "b_token_ledger_live",
        "producer": "B007_allocate_tokens_live.py",
        "path": "out/token_ledger_live.csv",
        "summary": "B live token ledger exists, has rows, and is fresh.",
        "min_rows": 1,
        "warn_hours": 1.0,
        "fail_hours": 3.0,
        "safe_repair_boundary": "B token proof only; no token correction or data rewrite from MOT.",
    },
    {
        "check": "b_token_cogs_ledger",
        "producer": "B025_build_token_cogs_ledger.py",
        "path": "out/token_cogs_ledger.csv",
        "summary": "B token COGS ledger exists, has rows, and is fresh.",
        "min_rows": 1,
        "warn_hours": 1.0,
        "fail_hours": 3.0,
        "safe_repair_boundary": "B token COGS proof only; no token correction or data rewrite from MOT.",
    },
    {
        "check": "b_token_shortages_by_sku",
        "producer": "B007_allocate_tokens_live.py",
        "path": "out/token_shortages_by_sku.csv",
        "summary": "B token shortage proof exists and is fresh. Zero rows can be healthy.",
        "min_rows": 0,
        "warn_hours": 1.0,
        "fail_hours": 3.0,
        "safe_repair_boundary": "B token-shortage proof only; do not apply token corrections from MOT.",
    },
    {
        "check": "b_pnl_daily",
        "producer": "D001_build_pnl_daily.py",
        "path": "out/pnl_daily.csv",
        "summary": "B-triggered daily P and L output exists, has rows, and is fresh enough for daytime proof.",
        "min_rows": 1,
        "warn_hours": 24.0,
        "fail_hours": 36.0,
        "safe_repair_boundary": "B P and L proof only; no finance data rewrite from MOT.",
    },
    {
        "check": "b_stock_snapshot_latest",
        "producer": "B901_refresh_stock_parking_state",
        "path": "out/parking/stock_snapshot_latest.csv",
        "summary": "B stock snapshot exists, has rows, and is fresh enough for daytime proof.",
        "min_rows": 1,
        "warn_hours": 4.0,
        "fail_hours": 8.0,
        "safe_repair_boundary": "B stock/parking proof only; no stock correction or local DB alignment from MOT.",
    },
    {
        "check": "b_parked_skus",
        "producer": "B901_refresh_stock_parking_state",
        "path": "out/parking/parked_skus.csv",
        "summary": "B parked SKU proof exists and is fresh. Zero parked rows can be healthy.",
        "min_rows": 0,
        "warn_hours": 4.0,
        "fail_hours": 8.0,
        "safe_repair_boundary": "B stock/parking proof only; no stock correction or local DB alignment from MOT.",
    },
]

E_EXPECTED_STEPS = [
    "E001_build_sales_velocity.py",
    "E002_build_roi_snapshot.py",
    "E003_build_restock_signals.py",
    "E004_build_performance_summary.py",
    "E005_build_study_report.py",
    "E006_build_sales_truth_reconciliation.py",
    "E007_build_sku_daily_sales_truth.py",
    "A015_build_system_health_check.py:profile=e",
]

E_CORE_OUTPUTS = [
    {
        "name": "sales_velocity",
        "producer": "E001_build_sales_velocity.py",
        "path": "out/sku_sales_velocity.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "window_days",
            "units_sold",
            "days_in_stock_est",
            "velocity_units_per_day",
            "v7",
            "v30",
            "v90",
            "v_blended",
            "available",
            "total_quantity",
            "asof_date",
        ],
    },
    {
        "name": "roi_snapshot",
        "producer": "E002_build_roi_snapshot.py",
        "path": "out/sku_roi_snapshot.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "window_days",
            "units_sold",
            "revenue_exvat_gbp",
            "cogs_exvat_gbp",
            "profit_exvat_gbp",
            "roi_exvat",
            "missing_cogs_units",
            "fx_missing_units",
            "asof_date",
        ],
    },
    {
        "name": "roi_snapshot_by_country",
        "producer": "E002_build_roi_snapshot.py",
        "path": "out/sku_roi_snapshot_by_country.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "window_days",
            "country_code",
            "units_sold",
            "revenue_exvat_gbp",
            "cogs_exvat_gbp",
            "profit_exvat_gbp",
            "roi_exvat",
            "missing_cogs_units",
            "fx_missing_units",
            "asof_date",
        ],
    },
    {
        "name": "restock_signals",
        "producer": "E003_build_restock_signals.py",
        "path": "out/sku_restock_signals.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "velocity_30d",
            "available",
            "total_quantity",
            "days_of_stock_left",
            "reorder_flag",
            "suggested_reorder_qty",
            "asof_date",
        ],
    },
    {
        "name": "performance_summary",
        "producer": "E004_build_performance_summary.py",
        "path": "out/sku_performance_summary.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "window_days",
            "units_sold",
            "velocity_units_per_day",
            "revenue_exvat_gbp",
            "profit_exvat_gbp",
            "roi_exvat",
            "days_of_stock_left",
            "reorder_flag",
            "units_sold_roi",
            "units_sold_truth_30d",
            "units_sold_velocity_30d",
            "units_sold_source",
            "expected_refund_cost_per_unit_gbp",
            "refund_unit_rate_30d",
            "refund_unit_rate_90d",
            "refund_units_30d",
            "sales_units_30d",
            "refund_cost_basis",
            "refund_proof_state",
            "refund_sample_confidence",
            "value_velocity_gbp_per_day",
        ],
    },
    {
        "name": "study_report",
        "producer": "E005_build_study_report.py",
        "path": "out/e_study_report.csv",
        "min_rows": 1,
        "columns": [
            "study_rank",
            "sku",
            "asof_date",
            "reorder_flag",
            "days_of_stock_left",
            "suggested_reorder_qty",
            "velocity_30d",
            "units_sold_30d",
            "units_sold_truth_30d",
            "revenue_exvat_gbp_30d",
            "profit_exvat_gbp_30d",
            "roi_exvat_30d",
            "latest_daily_truth_state",
        ],
    },
    {
        "name": "sales_truth_sku_30d",
        "producer": "E006_build_sales_truth_reconciliation.py",
        "path": "out/sales_truth_sku_30d_latest.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "window_days",
            "asof_date",
            "units_b_source",
            "revenue_b_source_gbp",
            "profit_b_source_gbp",
        ],
    },
    {
        "name": "sales_truth_reconciliation",
        "producer": "E006_build_sales_truth_reconciliation.py",
        "path": "out/sales_truth_reconciliation_latest.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "window_days",
            "asof_date",
            "units_b_source",
            "revenue_b_source_gbp",
            "profit_b_source_gbp",
            "units_e_output",
            "revenue_e_output_gbp",
            "profit_e_output_gbp",
            "units_delta",
            "revenue_delta_gbp",
            "profit_delta_gbp",
            "confidence_status",
            "root_cause_hint",
        ],
    },
    {
        "name": "sku_daily_sales_truth",
        "producer": "E007_build_sku_daily_sales_truth.py",
        "path": "out/sku_daily_sales_truth_latest.csv",
        "min_rows": 1,
        "columns": [
            "sku",
            "date",
            "source_state",
            "units",
            "revenue_gbp",
            "profit_gbp",
            "confidence_status",
        ],
    },
]

E_OUTPUT_BY_NAME = {str(item["name"]): item for item in E_CORE_OUTPUTS}

E_INPUT_PROOFS = [
    {
        "name": "orders",
        "producer": "B004_build_order_master.py",
        "path": "out/order_master.csv",
        "min_rows": 1,
        "warn_hours": 4.0,
        "fail_hours": 12.0,
    },
    {
        "name": "inventory",
        "producer": "A003_run_inventory_to_sheet.py",
        "path": "out/inventory_summaries.csv",
        "min_rows": 1,
        "warn_hours": E_DAILY_WARN_HOURS,
        "fail_hours": E_DAILY_FAIL_HOURS,
    },
    {
        "name": "cogs",
        "producer": "B025_build_token_cogs_ledger.py",
        "path": "out/token_cogs_ledger.csv",
        "min_rows": 1,
        "warn_hours": 4.0,
        "fail_hours": 12.0,
    },
    {
        "name": "fx",
        "producer": "B006_build_fx_ledgers.py",
        "path": "out/fx_rates_daily.csv",
        "min_rows": 1,
        "warn_hours": 12.0,
        "fail_hours": E_DAILY_FAIL_HOURS,
    },
    {
        "name": "fees",
        "producer": "B003_run_financial_events_level3.py",
        "path": "out/financial_events_level2.csv",
        "min_rows": 1,
        "warn_hours": 12.0,
        "fail_hours": E_DAILY_FAIL_HOURS,
    },
    {
        "name": "listing",
        "producer": "A001_run_listings_to_sheet.py",
        "path": "out/listing_offer_history.csv",
        "min_rows": 1,
        "warn_hours": E_DAILY_WARN_HOURS,
        "fail_hours": E_DAILY_FAIL_HOURS,
    },
    {
        "name": "refunds",
        "producer": "A006_refund_adjustments",
        "path": "out/refund_adjustment_history.csv",
        "min_rows": 1,
        "warn_hours": E_DAILY_WARN_HOURS,
        "fail_hours": E_DAILY_FAIL_HOURS,
    },
]

O_FEATURE_STAGES = [
    ("O contracts, paths, schemas, runner scaffolding", "built"),
    ("Product DB operator view and edit UI", "built"),
    ("Native restock source/recommendation/review files", "built"),
    ("Legacy Purchase List import", "bridge"),
    ("E-to-O net-fee economics", "bridge"),
    ("Reorder price-proof layer", "proof_only"),
    ("Market-refresh candidate queue", "bridge"),
    ("Human approval decision capture", "proof_only"),
    ("PO draft builder", "proof_only"),
    ("Ordered stock and receiving", "proof_only"),
    ("Send-to-Amazon flow", "not_started"),
    ("Closed-loop feedback to A/B/E", "not_started"),
    ("Single connected workflow view", "not_verified"),
    ("Pack and supplier readiness", "not_verified"),
    ("Running market proof while H owns market files", "unsafe_blocker"),
]

O_ACTIVE_PROOF_OUTPUTS = [
    ("restock_source_view", "out/systems/O/live/restock_source_view.csv", "built", 1),
    ("restock_recommendations_live", "out/systems/O/live/restock_recommendations_live.csv", "built", 1),
    ("restock_review_queue", "out/systems/O/live/restock_review_queue.csv", "built", 1),
    ("reorder_input_coverage_report", "out/systems/O/live/reorder_input_coverage_report.csv", "built", 1),
    ("legacy_purchase_list_bridge", "out/systems/O/live/legacy_purchase_list_bridge.csv", "bridge", 1),
    ("legacy_purchase_list_bridge_health", "out/systems/O/live/legacy_purchase_list_bridge_health.csv", "bridge", 1),
    ("restock_profit_checks_live", "out/systems/O/live/restock_profit_checks_live.csv", "proof_only", 1),
    ("restock_profit_check_health", "out/systems/O/live/restock_profit_check_health.csv", "proof_only", 1),
    ("restock_market_refresh_candidates_live", "out/systems/O/live/restock_market_refresh_candidates_live.csv", "bridge", 0),
]

O_DOWNSTREAM_PROOF_OUTPUTS = [
    ("restock_decisions_log", "out/systems/O/live/restock_decisions_log.csv", "proof_only", 0),
    ("purchase_orders_live", "out/systems/O/live/purchase_orders_live.csv", "proof_only", 0),
    ("purchase_order_lines_live", "out/systems/O/live/purchase_order_lines_live.csv", "proof_only", 0),
    ("purchase_order_draft_holds", "out/systems/O/live/purchase_order_draft_holds.csv", "proof_only", 0),
    ("ordered_stock_state", "out/systems/O/live/ordered_stock_state.csv", "proof_only", 0),
    ("receiving_events", "out/systems/O/live/receiving_events.csv", "proof_only", 0),
    ("receiving_event_holds", "out/systems/O/live/receiving_event_holds.csv", "proof_only", 0),
    ("send_to_amazon_queue", "out/systems/O/live/send_to_amazon_queue.csv", "not_started", 0),
    ("send_to_amazon_handoff_log", "out/systems/O/live/send_to_amazon_handoff_log.csv", "not_started", 0),
    ("send_to_amazon_handoff_holds", "out/systems/O/live/send_to_amazon_handoff_holds.csv", "not_started", 0),
]


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]


def _latest_csv_row(rows: list[dict[str, str]], *, time_field: str = "observed_utc") -> dict[str, str]:
    if not rows:
        return {}
    dated: list[tuple[datetime, int, dict[str, str]]] = []
    for index, row in enumerate(rows):
        parsed = parse_utc(str(row.get(time_field, "")))
        if parsed is not None:
            dated.append((parsed, index, row))
    if dated:
        return sorted(dated, key=lambda item: (item[0], item[1]))[-1][2]
    return rows[-1]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def file_age_hours(path: Path, now: datetime) -> float | None:
    if not path.exists():
        return None
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None
    return max((now - mtime).total_seconds() / 3600.0, 0.0)


def csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for _row in reader)
    except OSError:
        return None


def csv_headers(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or [])
    except OSError:
        return None


def read_csv_dicts(path: Path) -> list[dict[str, str]] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]
    except OSError:
        return None


def latest_manifest(manifest_root: Path) -> tuple[dict[str, Any], Path | None]:
    if not manifest_root.exists():
        return {}, None
    candidates = sorted(manifest_root.rglob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        return payload, candidate
    return {}, None


def status_from_age(age_hours: float | None, *, warn_hours: float, fail_hours: float) -> str:
    if age_hours is None:
        return "fail"
    if age_hours >= fail_hours:
        return "fail"
    if age_hours >= warn_hours:
        return "warn"
    return "ok"


def _severity(status: str) -> str:
    if status in {"fail", "decision_needed"}:
        return "blocker"
    if status == "warn":
        return "warning"
    return "info"


def _age_text(age: float | None) -> str:
    return "" if age is None else f"{age:.2f}"


def _seconds_text(seconds: float | None) -> str:
    return "" if seconds is None else f"{seconds:.2f}"


def _work_item_id(flow: str, check: str) -> str:
    clean = "".join(char if char.isalnum() else "_" for char in check).strip("_").upper()
    return f"MOT_{flow}_{clean}"


def _retest_command(flow: str) -> str:
    return f"python -m sellerone_manager.app --hourly-mot --mot-flow {flow}"


def mot_row(
    *,
    observed_utc: str,
    check: str,
    flow: str = "A",
    status: str,
    severity: str,
    value: str,
    producer: str = "",
    expected_output: str = "",
    actual_proof: str = "",
    age_hours: str = "",
    row_count: str = "",
    source_path: str = "",
    summary: str,
    root_cause_guess: str = "",
    manager_action: str,
    luke_action_required: str = "0",
    retest_command: str = "",
    safe_repair_boundary: str = "",
    changed_since_previous: str = "",
    previous_status: str = "",
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "flow": flow,
        "check": check,
        "producer": producer,
        "expected_output": expected_output,
        "status": status,
        "severity": severity,
        "value": value,
        "actual_proof": actual_proof,
        "age_hours": age_hours,
        "row_count": row_count,
        "source_path": source_path,
        "summary": summary,
        "root_cause_guess": root_cause_guess,
        "manager_action": manager_action,
        "luke_action_required": luke_action_required,
        "retest_command": retest_command or _retest_command(flow),
        "safe_repair_boundary": safe_repair_boundary,
        "changed_since_previous": changed_since_previous,
        "previous_status": previous_status,
    }


def build_a_hourly_mot(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    rows: list[dict[str, str]] = []

    manifest, manifest_path = latest_manifest(base / "out" / "manifests" / "A")
    handoff_payload = _read_json(base / "out" / "systems" / "A" / "live" / "a_maintenance_handoff_latest.json")
    if not manifest_path:
        rows.append(
            mot_row(
                observed_utc=observed,
                check="a_latest_manifest",
                status="fail",
                severity="blocker",
                value="missing",
                producer="scripts/cycles/run_A_all.py",
                expected_output="out/manifests/A/**/*.json",
                actual_proof="manifest_missing",
                source_path="out/manifests/A",
                summary="No A manifest was found.",
                root_cause_guess="A has no durable run proof.",
                manager_action="Create a Codex task to inspect why A has no durable run proof.",
                safe_repair_boundary="A runner proof only; do not run A unless a flow-owned proof window is approved.",
            )
        )
    else:
        end_time = parse_utc(str(manifest.get("end_time", "")))
        age = max((now - end_time).total_seconds() / 3600.0, 0.0) if end_time else file_age_hours(manifest_path, now)
        final_state = str(manifest.get("final_state", "") or "unknown")
        interrupted_pending = _a_interrupted_pending_normal_proof(manifest, handoff_payload)
        status = status_from_age(age, warn_hours=A_DAILY_WARN_HOURS, fail_hours=A_DAILY_FAIL_HOURS)
        if final_state not in {"completed", "success"}:
            status = "not_checked" if interrupted_pending and status != "fail" else "fail"
        value = "interrupted_pending_next_normal_a_run" if interrupted_pending and status == "not_checked" else final_state
        root_cause = ""
        manager_action = "No action; latest A manifest is complete and fresh."
        if status == "not_checked" and interrupted_pending:
            root_cause = "A proof run was interrupted after a safe maintenance handoff; next normal A-owned run must prove completion."
            manager_action = "Park this A proof row until the next normal A-owned run; do not run A or A015 from MOT."
        elif status != "ok":
            root_cause = "A manifest is stale or not completed."
            manager_action = "If fail, inspect the manifest stopped step before trusting downstream data."
        rows.append(
            mot_row(
                observed_utc=observed,
                check="a_latest_manifest",
                status=status,
                severity=_severity(status),
                value=value,
                producer="scripts/cycles/run_A_all.py",
                expected_output="out/manifests/A/**/*.json",
                actual_proof=f"manifest_age_hours={_age_text(age)};final_state={final_state}",
                age_hours=_age_text(age),
                source_path=str(manifest_path),
                summary="Latest A manifest proves whether A finished and how old that proof is.",
                root_cause_guess=root_cause,
                manager_action=manager_action,
                safe_repair_boundary="A runner proof only; do not run A unless a flow-owned proof window is approved.",
            )
        )
        configured = int(manifest.get("configured_step_count", 0) or 0)
        recorded = int(manifest.get("recorded_step_count", 0) or 0)
        traversal_status = "ok" if configured and recorded >= configured else "fail"
        traversal_value = f"{recorded}/{configured}"
        traversal_root_cause = "A did not traverse every configured step." if traversal_status != "ok" else ""
        traversal_manager_action = "If fail, create a bounded A repair task for the first missing or stopped step."
        if traversal_status == "fail" and interrupted_pending:
            traversal_status = "not_checked"
            traversal_value = f"interrupted_pending_next_normal_a_run:{recorded}/{configured}"
            traversal_root_cause = "A proof run was interrupted before every configured step could be recorded."
            traversal_manager_action = "Park this A traversal proof until the next normal A-owned run; do not run A or A015 from MOT."
        rows.append(
            mot_row(
                observed_utc=observed,
                check="a_manifest_step_traversal",
                status=traversal_status,
                severity=_severity(traversal_status),
                value=traversal_value,
                producer="scripts/cycles/run_A_all.py",
                expected_output="manifest steps",
                actual_proof=f"recorded={recorded};configured={configured}",
                source_path=str(manifest_path),
                summary="A should record every configured step, even if a step was skipped for a known reason.",
                root_cause_guess=traversal_root_cause,
                manager_action=traversal_manager_action,
                safe_repair_boundary="A runner manifest finalizer only; no worker data changes.",
            )
        )

    step_map = {
        str(step.get("name", "")): step
        for step in manifest.get("steps", [])
        if isinstance(step, dict) and str(step.get("name", "")).strip()
    }

    for item in A_REQUIRED_OUTPUTS:
        path = base / item["path"]
        age = file_age_hours(path, now)
        rows_count = csv_row_count(path)
        status = status_from_age(age, warn_hours=A_DAILY_WARN_HOURS, fail_hours=A_DAILY_FAIL_HOURS)
        min_rows = int(item.get("min_rows", 0) or 0)
        root_cause = ""
        if rows_count is None:
            status = "fail"
            value = "missing_or_unreadable"
            root_cause = "Expected A output is missing or cannot be read."
        elif rows_count < min_rows:
            status = "fail"
            value = f"rows_below_min:{rows_count}<{min_rows}"
            root_cause = "Expected A output exists but has too few rows."
        else:
            value = "fresh_enough" if status == "ok" else "stale"
            if status != "ok":
                root_cause = "Expected A output is stale."

        producer_name = str(item.get("producer", "")).strip()
        producer = step_map.get(producer_name, {})
        producer_status = str(producer.get("step_status", "") or "").strip()
        producer_verification = str(producer.get("verification_status", "") or "").strip()
        producer_notes = str(producer.get("notes", "") or "").strip()
        manager_action = "If stale or missing, treat downstream flows as using old A facts until A proof is current."
        if status != "ok" and (producer_status or producer_verification):
            value = f"{value};producer={producer_status or 'unknown'}:{producer_verification or 'unknown'}"
            if producer_status == "skipped":
                root_cause = "Producer step was skipped, so local source facts did not refresh."
                manager_action = (
                    "Create an A task to separate local data refresh from legacy Sheet writing, "
                    "because this source fact did not refresh after the producer step was skipped."
                )
            elif producer_notes:
                root_cause = "Producer step notes explain why output is not trusted."
                manager_action = "Inspect the producer step notes before trusting downstream data: " + producer_notes[:180]

        rows.append(
            mot_row(
                observed_utc=observed,
                check=str(item["check"]),
                status=status,
                severity=_severity(status),
                value=value,
                producer=producer_name,
                expected_output=str(item["path"]),
                actual_proof=f"exists={1 if path.exists() else 0};rows={'' if rows_count is None else rows_count};age_hours={_age_text(age)}",
                age_hours=_age_text(age),
                row_count="" if rows_count is None else str(rows_count),
                source_path=str(path),
                summary=str(item["summary"]),
                root_cause_guess=root_cause,
                manager_action=manager_action,
                safe_repair_boundary=str(item.get("safe_repair_boundary", "")),
            )
        )

    rows.extend(_sql_table_rows(base=base, observed_utc=observed))
    rows.extend(_proof_only_output_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_proof_only_sql_table_rows(base=base, observed_utc=observed))
    rows.extend(_a_maintenance_handoff_rows(base=base, observed_utc=observed, manifest=manifest, manifest_path=manifest_path))
    rows.extend(_a_lock_rows(base=base, observed_utc=observed, now=now))
    return _result_from_rows(observed, "A", rows)


def build_b_hourly_mot(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    rows: list[dict[str, str]] = []

    manifest, manifest_path = latest_manifest(base / "out" / "manifests" / "B")
    rows.extend(_b_manifest_rows(base=base, observed_utc=observed, now=now, manifest=manifest, manifest_path=manifest_path))
    rows.extend(_b_required_output_rows(base=base, observed_utc=observed, now=now, manifest=manifest, manifest_path=manifest_path))
    rows.extend(_b_stock_receipt_token_sync_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_b_ownership_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_b_maintenance_marker_rows(base=base, observed_utc=observed))
    rows.extend(_b_sellerboard_email_intake_rows(base=base, observed_utc=observed))
    rows.extend(_b_refund_pnl_bridge_rows(base=base, observed_utc=observed))
    rows.extend(_b_refund_return_token_bridge_rows(base=base, observed_utc=observed))
    rows.extend(_b_return_cogs_residual_review_rows(base=base, observed_utc=observed))
    rows.extend(_b_return_token_matching_audit_rows(base=base, observed_utc=observed))
    rows.extend(_b_return_token_repair_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_refund_return_warning_workpack_rows(base=base, observed_utc=observed))
    rows.extend(_b_fallback_token_cost_audit_rows(base=base, observed_utc=observed))
    rows.extend(_b_fallback_cost_proof_reconciliation_rows(base=base, observed_utc=observed))
    rows.extend(_b_amazon_return_coverage_audit_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_allocation_gap_audit_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_order_recovery_proof_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_order_recovery_fetch_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_sale_allocation_repair_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_sale_allocation_repair_apply_rows(base=base, observed_utc=observed))
    rows.extend(_b_refund_token_reproof_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_b008_token_ledger_gap_review_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_return_status_conflict_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_original_return_status_apply_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_disposition_conflict_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_disposition_conflict_decision_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_disposition_correction_impact_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_disposition_correction_apply_preview_rows(base=base, observed_utc=observed))
    rows.extend(_b_historical_replacement_stock_proof_rows(base=base, observed_utc=observed))
    rows.extend(_b_no_replacement_shortage_exception_review_rows(base=base, observed_utc=observed))
    rows.extend(_b_disposition_correction_swap_apply_rows(base=base, observed_utc=observed))
    rows.extend(_b_sellerboard_bridge_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_b_refund_fee_shipping_gap_review_rows(base=base, observed_utc=observed))
    rows.extend(_b_level3_fee_shipping_api_proof_map_rows(base=base, observed_utc=observed))
    rows.extend(_b_marketplace_coverage_rows(base=base, observed_utc=observed))
    rows.extend(_b_order_recovery_rows(base=base, observed_utc=observed))
    rows.extend(_b_order_promotion_rows(base=base, observed_utc=observed))
    rows.extend(_b_old_checklist_clue_rows(base=base, observed_utc=observed))
    rows.extend(_b_completion_gate_rows(rows=rows, observed_utc=observed))
    result = _result_from_rows(observed, "B", rows)
    result["quiet_autonomy_active"] = quiet_autonomy_active(base)
    return result


def build_e_hourly_mot(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    rows: list[dict[str, str]] = []

    manifest, manifest_path = latest_manifest(base / "out" / "manifests" / "E")
    rows.extend(_e_manifest_rows(base=base, observed_utc=observed, now=now, manifest=manifest, manifest_path=manifest_path))
    rows.extend(_e_run_log_rows(base=base, observed_utc=observed, now=now, manifest=manifest))
    rows.extend(_e_cadence_control_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_e_input_readiness_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_e_core_outputs_fresh_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_e_core_row_count_rows(base=base, observed_utc=observed))
    rows.extend(_e_schema_contract_rows(base=base, observed_utc=observed))
    rows.extend(_e_cross_output_alignment_rows(base=base, observed_utc=observed))
    rows.extend(_e_confidence_coverage_rows(base=base, observed_utc=observed))
    rows.extend(_e_health_profile_rows(base=base, observed_utc=observed, now=now, manifest=manifest))
    rows.extend(_e_lock_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_e_optional_publish_rows(base=base, observed_utc=observed, now=now))
    return _result_from_rows(observed, "E", rows)


H_PROOF_ONLY_BOUNDARY = (
    "H manager proof only; no H run, scheduler ownership change, publish, price change, "
    "queue edit, Sheet write, local DB alignment, output deletion, or worker restart."
)
H_SUCCESS_STATES = {"ok", "success", "succeeded", "complete", "completed", "finalized", "finalised"}
H_FAIL_STATES = {"fail", "failed", "error", "blocked", "timeout", "timed_out"}
H_BLANK_WRITE_STATUSES = {"", "unknown", "null", "none", "nan"}
H_RELIABILITY_WINDOW_SIZE = 10
H_RELIABILITY_CLEAN_TARGET = 8
H_STAGED_STORAGE_RULE_ID = "h_staged_publish_snapshots"
H_STAGED_LEDGER_POLICY = "h_staged_retention"


def build_h_hourly_mot(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    rows: list[dict[str, str]] = []

    manifest, manifest_path = latest_manifest(base / "out" / "manifests" / "H")
    terminal_path = base / "out" / "systems" / "H" / "live" / "H_cycle_last_terminal_info.txt"
    publish_path = base / "out" / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt"
    terminal = _read_key_value_fields(terminal_path)
    publish = _read_key_value_fields(publish_path)

    rows.extend(
        _h_latest_manifest_rows(
            base=base,
            observed_utc=observed,
            now=now,
            manifest=manifest,
            manifest_path=manifest_path,
        )
    )
    rows.extend(
        _h_terminal_publish_rows(
            observed_utc=observed,
            terminal=terminal,
            terminal_path=terminal_path,
            publish=publish,
            publish_path=publish_path,
        )
    )
    rows.extend(_h_decision_execution_rows(base=base, observed_utc=observed))
    rows.extend(_h_market_context_rows(base=base, observed_utc=observed))
    rows.extend(_h_floor_ceiling_rows(base=base, observed_utc=observed))
    rows.extend(_h_token_floor_source_rows(base=base, observed_utc=observed))
    rows.extend(_h_lock_rows(base=base, observed_utc=observed, now=now))
    rows.extend(
        _h_boundary_finalizer_rows(
            base=base,
            observed_utc=observed,
            manifest=manifest,
            manifest_path=manifest_path,
            terminal=terminal,
            terminal_path=terminal_path,
        )
    )
    rows.extend(_h_reliability_window_rows(base=base, observed_utc=observed))
    rows.extend(_h_health_clue_rows(base=base, observed_utc=observed))
    rows.extend(_h_storage_cleanup_rows(base=base, observed_utc=observed))
    rows.extend(_h_defensive_listing_protection_rows(base=base, observed_utc=observed))
    rows.extend(_h_manager_readiness_rows(rows=rows, observed_utc=observed))
    return _result_from_rows(observed, "H", rows)


def _read_key_value_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return _parse_pipe_fields(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return {"_read_error": "1"}


def _h_norm_run_id(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("H_"):
        text = text[2:]
    if text.endswith("Z"):
        text = text[:-1]
    return text


def _h_state(value: object) -> str:
    return str(value or "").strip().lower()


def _h_source(*paths: Path | None) -> str:
    return ";".join(str(path) for path in paths if path is not None)


def _h_storage_registry_rule(base: Path) -> tuple[dict[str, Any], Path, str]:
    path = base / "project_control" / "log_housekeeping_registry.json"
    if not path.exists():
        return {}, path, "registry_missing"
    payload = _read_json(path)
    if payload.get("_read_error"):
        return {}, path, "registry_unreadable"
    rules = payload.get("rules", [])
    if not isinstance(rules, list):
        return {}, path, "registry_rules_unreadable"
    for rule in rules:
        if isinstance(rule, dict) and str(rule.get("id", "")).strip() == H_STAGED_STORAGE_RULE_ID:
            return rule, path, ""
    return {}, path, "registry_rule_missing"


def _h_storage_registry_cap(rule: dict[str, Any]) -> int | None:
    retention = rule.get("retention", {})
    if not isinstance(retention, dict):
        return None
    raw = retention.get("max_file_count")
    try:
        cap = int(float(str(raw)))
    except (TypeError, ValueError):
        return None
    return cap if cap > 0 else None


def _h_cleanup_ledger_entry(ledger_path: Path) -> tuple[dict[str, Any], str]:
    if not ledger_path.exists() or ledger_path.stat().st_size == 0:
        return {}, "cleanup_ledger_missing"
    try:
        lines = ledger_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {}, "cleanup_ledger_unreadable"
    saw_json_error = False
    for raw in reversed(lines):
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            saw_json_error = True
            continue
        if isinstance(payload, dict) and str(payload.get("policy", "")).strip() == H_STAGED_LEDGER_POLICY:
            return payload, ""
    if saw_json_error and not any(line.strip().startswith("{") for line in lines):
        return {}, "cleanup_ledger_unreadable"
    return {}, "staged_cleanup_receipt_missing"


def _h_count_cap_from_reason(reason: object) -> int | None:
    match = re.search(r"(?:^|;)count_cap=(?P<cap>\d+)(?:;|$)", str(reason or ""))
    if not match:
        return None
    try:
        return int(match.group("cap"))
    except ValueError:
        return None


def _h_staged_snapshot_state(staged_path: Path) -> tuple[int, int, list[str], str]:
    if not staged_path.exists():
        return 0, 0, [], "staged_dir_missing"
    try:
        entries = list(staged_path.iterdir())
    except OSError:
        return -1, -1, [], "staged_dir_unreadable"
    dirs = sorted([path for path in entries if path.is_dir()], key=lambda path: path.name)
    newest = [path.name for path in dirs[-5:]]
    return len(entries), len(dirs), newest, ""


def _h_latest_manifest_rows(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    manifest: dict[str, Any],
    manifest_path: Path | None,
) -> list[dict[str, str]]:
    if not manifest_path:
        status = "fail"
        value = "manifest_missing"
        age = None
        root_cause = "No readable H manifest exists for the manager to inspect."
        actual = "missing"
    else:
        final_state = _h_state(manifest.get("final_state", ""))
        run_id = str(manifest.get("run_id", "") or "").strip()
        age = file_age_hours(manifest_path, now)
        if final_state in H_FAIL_STATES:
            status = "fail"
            value = f"run_id={run_id};final_state={final_state}"
            root_cause = "Latest H manifest says the H run failed."
        elif final_state not in H_SUCCESS_STATES:
            status = "fail"
            value = f"run_id={run_id};final_state={final_state or 'blank'}"
            root_cause = "Latest H manifest does not expose a clear final state."
        elif age is not None and age >= H_MANIFEST_WARN_HOURS:
            status = "warn"
            value = f"run_id={run_id};final_state={final_state};age_hours={_age_text(age)}"
            root_cause = "Latest H manifest is readable but older than the manager freshness target."
        else:
            status = "ok"
            value = f"run_id={run_id};final_state={final_state}"
            root_cause = ""
        actual = value
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_latest_manifest_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="run_H_pricing_cycle.py",
            expected_output="latest readable H manifest with clear final_state",
            actual_proof=actual,
            age_hours=_age_text(age),
            source_path=str(manifest_path or (base / "out" / "manifests" / "H")),
            summary="Latest H manifest proves whether H reached a clear run boundary.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, create a bounded H manifest/finalizer proof task. "
                "Do not run H from MOT."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_terminal_publish_rows(
    *,
    observed_utc: str,
    terminal: dict[str, str],
    terminal_path: Path,
    publish: dict[str, str],
    publish_path: Path,
) -> list[dict[str, str]]:
    terminal_state = _h_state(terminal.get("state", ""))
    terminal_publish = _h_state(terminal.get("publish_status", ""))
    publish_status = _h_state(publish.get("status", ""))
    terminal_run = _h_norm_run_id(terminal.get("run_id", ""))
    publish_run = _h_norm_run_id(publish.get("run_id", ""))
    failure_code = str(terminal.get("failure_code", "") or "").strip()
    failure_detail = str(terminal.get("failure_detail", "") or "").strip()
    if not terminal:
        status = "fail"
        value = "terminal_missing"
        root_cause = "H terminal marker is missing."
    elif terminal.get("_read_error") == "1":
        status = "fail"
        value = "terminal_unreadable"
        root_cause = "H terminal marker cannot be read."
    elif terminal_state not in {"finalized", "finalised"}:
        status = "fail"
        value = f"terminal_state={terminal_state or 'blank'}"
        root_cause = "H terminal marker does not show a finalized state."
    elif failure_code or failure_detail:
        status = "fail"
        value = f"failure_code={failure_code or 'blank'}"
        root_cause = "H terminal marker carries failure detail."
    elif not publish:
        status = "fail"
        value = "publish_missing"
        root_cause = "H terminal marker finalized, but publish proof is missing."
    elif publish.get("_read_error") == "1":
        status = "fail"
        value = "publish_unreadable"
        root_cause = "H publish marker cannot be read."
    elif terminal_run and publish_run and terminal_run != publish_run:
        status = "fail"
        value = f"terminal_run={terminal_run};publish_run={publish_run}"
        root_cause = "H terminal and publish markers point at different runs."
    elif terminal_publish != "ok" or publish_status != "ok":
        status = "fail"
        value = f"terminal_publish={terminal_publish or 'blank'};publish_status={publish_status or 'blank'}"
        root_cause = "H terminal or publish proof does not say publish completed cleanly."
    else:
        status = "ok"
        value = f"run_id={terminal_run};publish_status=ok"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_terminal_publish_truth",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H finalizer and publish marker",
            expected_output="terminal finalized and publish status ok for same run",
            actual_proof=(
                f"terminal_run={terminal_run};terminal_state={terminal_state};"
                f"terminal_publish={terminal_publish};publish_run={publish_run};publish_status={publish_status}"
            ),
            source_path=_h_source(terminal_path, publish_path),
            summary="H terminal and publish markers must agree before H is manager-proven.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, package a bounded H terminal/publish proof task. "
                "Do not publish or rerun H from MOT."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_decision_execution_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    decision_path = base / "data" / "decision_log.csv"
    execution_path = base / "data" / "execution_log.csv"
    snapshot_path = base / "out" / "phase1_runtime_floor_snapshot_latest.csv"
    decision_count = csv_row_count(decision_path)
    execution_count = csv_row_count(execution_path)
    snapshot_rows = read_csv_dicts(snapshot_path)
    required = {"sku", "execution_write_status"}
    headers = set(csv_headers(snapshot_path) or [])
    missing_headers = sorted(required - headers)
    blank_statuses = 0
    if snapshot_rows:
        blank_statuses = sum(
            1
            for row in snapshot_rows
            if str(row.get("execution_write_status", "") or "").strip().lower() in H_BLANK_WRITE_STATUSES
        )
    if decision_count is None or execution_count is None or snapshot_rows is None:
        status = "fail"
        value = "decision_or_execution_proof_missing"
        root_cause = "H decision, execution, or runtime snapshot proof is missing."
    elif not decision_count or not execution_count or not snapshot_rows:
        status = "fail"
        value = f"decision_rows={decision_count};execution_rows={execution_count};snapshot_rows={len(snapshot_rows)}"
        root_cause = "H decision/execution proof exists but has no rows."
    elif missing_headers:
        status = "fail"
        value = f"missing_headers={','.join(missing_headers)}"
        root_cause = "H runtime snapshot is missing required manager columns."
    elif blank_statuses:
        status = "fail"
        value = f"blank_write_status_rows={blank_statuses};snapshot_rows={len(snapshot_rows)}"
        root_cause = "H runtime snapshot has blank execution write-status proof."
    else:
        status = "ok"
        value = f"decision_rows={decision_count};execution_rows={execution_count};snapshot_rows={len(snapshot_rows)}"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_decision_execution_rows",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H110/phase1 runtime",
            expected_output="decision rows, execution rows, and explicit execution_write_status values",
            actual_proof=value,
            row_count=str(len(snapshot_rows or [])),
            source_path=_h_source(decision_path, execution_path, snapshot_path),
            summary="H should leave explicit decision and execution proof for the manager.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, create a bounded H proof task for the producer of the blank/missing rows. "
                "Do not mask downstream outputs."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "ok"}


def _h_market_context_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    scope_path = base / "out" / "phase1_sku_scope.csv"
    snapshot_path = base / "out" / "phase1_runtime_floor_snapshot_latest.csv"
    offer_path = base / "out" / "listing_offer_history.csv"
    seller_path = base / "out" / "listing_offer_seller_observation_history.csv"
    scope_count = csv_row_count(scope_path)
    offer_count = csv_row_count(offer_path)
    seller_count = csv_row_count(seller_path)
    snapshot_rows = read_csv_dicts(snapshot_path)
    missing_context = 0
    if snapshot_rows:
        for row in snapshot_rows:
            if _h_requires_market_context_proof(row) and not _h_truthy(row.get("current_cycle_market_data_present", "")):
                missing_context += 1
    if scope_count is None or snapshot_rows is None:
        status = "fail"
        value = "scope_or_snapshot_missing"
        root_cause = "H scope or runtime snapshot proof is missing."
    elif offer_count is None or seller_count is None:
        status = "fail"
        value = "offer_context_missing"
        root_cause = "H market/offer proof files are missing."
    elif not scope_count or not snapshot_rows:
        status = "fail"
        value = f"scope_rows={scope_count};snapshot_rows={len(snapshot_rows)}"
        root_cause = "H has no readable scope or runtime rows for market context inspection."
    elif missing_context:
        status = "fail"
        value = f"priced_rows_missing_market_context={missing_context}"
        root_cause = "H attempted or recorded current-cycle decisions without market context proof."
    elif not offer_count or not seller_count:
        status = "warn"
        value = f"scope_rows={scope_count};offer_rows={offer_count};seller_rows={seller_count}"
        root_cause = "H market proof is readable but thin."
    else:
        status = "ok"
        value = f"scope_rows={scope_count};offer_rows={offer_count};seller_rows={seller_count}"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_market_context_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H004/H offer collection",
            expected_output="scope rows plus market and seller offer proof",
            actual_proof=value,
            row_count=str(scope_count or 0),
            source_path=_h_source(scope_path, snapshot_path, offer_path, seller_path),
            summary="H market context should explain the rows H is pricing or observing.",
            root_cause_guess=root_cause,
            manager_action="If fail, package a bounded H market-context proof task. Do not run H from MOT.",
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_requires_market_context_proof(row: dict[str, str]) -> bool:
    decision = str(row.get("current_cycle_decision", "") or "").strip().lower()
    if not decision:
        return False
    if decision == "skip_no_market_data":
        return False
    return True


def _h_floor_ceiling_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    snapshot_path = base / "out" / "phase1_runtime_floor_snapshot_latest.csv"
    trace_path = base / "out" / "h_floor_truth_trace.csv"
    snapshot_rows = read_csv_dicts(snapshot_path)
    trace_count = csv_row_count(trace_path)
    headers = set(csv_headers(snapshot_path) or [])
    required_headers = {"sku", "execution_hard_floor_gbp", "execution_final_ceiling_landed_gbp"}
    missing_headers = sorted(required_headers - headers)
    blank_floor = 0
    blank_ceiling = 0
    if snapshot_rows:
        for row in snapshot_rows:
            if not _h_requires_floor_ceiling_proof(row):
                continue
            floor_value = str(row.get("execution_hard_floor_gbp", "") or row.get("trace_floor_total_gbp", "")).strip()
            ceiling_value = str(
                row.get("execution_final_ceiling_landed_gbp", "") or row.get("true_binding_ceiling_gbp", "")
            ).strip()
            if not floor_value:
                blank_floor += 1
            if not ceiling_value:
                blank_ceiling += 1
    if snapshot_rows is None or trace_count is None:
        status = "fail"
        value = "floor_or_ceiling_proof_missing"
        root_cause = "H floor/ceiling proof is missing."
    elif not snapshot_rows or not trace_count:
        status = "fail"
        value = f"snapshot_rows={len(snapshot_rows)};floor_trace_rows={trace_count}"
        root_cause = "H floor/ceiling proof exists but has no rows."
    elif missing_headers:
        status = "fail"
        value = f"missing_headers={','.join(missing_headers)}"
        root_cause = "H runtime floor snapshot is missing required safety columns."
    elif blank_floor or blank_ceiling:
        status = "fail"
        value = f"blank_floor_rows={blank_floor};blank_ceiling_rows={blank_ceiling}"
        root_cause = "H has current-cycle pricing rows without populated floor or ceiling proof."
    else:
        status = "ok"
        value = f"snapshot_rows={len(snapshot_rows)};floor_trace_rows={trace_count}"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_floor_ceiling_safety_fields",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H floor truth / runtime snapshot",
            expected_output="floor and ceiling safety values for current H rows",
            actual_proof=value,
            row_count=str(len(snapshot_rows or [])),
            source_path=_h_source(snapshot_path, trace_path),
            summary="H floor and ceiling rails must be visible before repricing proof can be trusted.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, create a bounded H floor/ceiling proof task at the source. "
                "Do not change prices from MOT."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_requires_floor_ceiling_proof(row: dict[str, str]) -> bool:
    if _h_truthy(row.get("write_attempted_flag", "")):
        return True
    write_status = str(row.get("execution_write_status", "") or "").strip().upper()
    if write_status and write_status not in {"NO_WRITE_REQUIRED", "READ_ONLY_NO_WRITE"}:
        return True
    truth_status = str(row.get("truth_status", "") or "").strip().upper()
    if truth_status.startswith("WRITE_") or truth_status.startswith("SUPP_"):
        return True
    return False


H_FLOOR_CLEAN_SOURCE_STATES = {"clean", "receipt_proved"}
H_FLOOR_RISK_SOURCE_STATES = {
    "source_token_proved",
    "batch_link_proof_needed",
    "weak_fallback",
    "unproved",
    "unknown",
}


def _h_token_floor_source_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    snapshot_path = base / "out" / "phase1_runtime_floor_snapshot_latest.csv"
    trace_path = base / "out" / "h_floor_truth_trace.csv"
    audit_path = base / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv"
    reconciliation_path = base / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv"
    token_ledger_path, selected_tokens = _h_selected_token_cost_sources(base)
    snapshot_rows = read_csv_dicts(snapshot_path)
    trace_rows = read_csv_dicts(trace_path)
    audit_by_token = _h_fallback_cost_audit_by_token(audit_path)
    reconciliation_by_token = _h_fallback_cost_reconciliation_by_token(reconciliation_path)

    if trace_rows is None:
        status = "fail"
        value = "floor_trace_missing_or_unreadable"
        row_count = "0"
        root_cause = "H floor source proof is missing, so the manager cannot tell whether the floor source is safe."
        actual_proof = value
    else:
        active_skus = _h_floor_source_active_skus(snapshot_rows, trace_rows)
        latest_trace_by_sku = _h_latest_trace_rows_by_sku(trace_rows)
        snapshot_by_sku = {
            str(row.get("sku", "") or "").strip().upper(): row
            for row in (snapshot_rows or [])
            if str(row.get("sku", "") or "").strip()
        }
        clean_rows = 0
        risky_rows: list[dict[str, str]] = []
        unknown_rows: list[dict[str, str]] = []
        active_conflict_no_clean_floor_rows: list[dict[str, str]] = []
        fallback_rows = 0
        batch_link_needed_rows = 0

        for sku in active_skus:
            trace_row = latest_trace_by_sku.get(sku, {})
            snapshot_row = snapshot_by_sku.get(sku, {})
            if _h_trace_has_token_selection_conflict(trace_row) and _h_missing_clean_floor(snapshot_row, trace_row):
                active_conflict_no_clean_floor_rows.append({"sku": sku, **trace_row})
            proof = _h_floor_source_proof(
                trace_row,
                selected_tokens.get(sku, {}),
                audit_by_token,
                reconciliation_by_token,
            )
            if proof.get("is_fallback") == "1":
                fallback_rows += 1
            state = proof.get("proof_state", "unknown")
            if state == "batch_link_proof_needed":
                batch_link_needed_rows += 1
            if state in H_FLOOR_CLEAN_SOURCE_STATES:
                clean_rows += 1
            elif state in H_FLOOR_RISK_SOURCE_STATES:
                risky_rows.append({"sku": sku, **proof})
                if state == "unknown":
                    unknown_rows.append({"sku": sku, **proof})
            else:
                risky_rows.append({"sku": sku, **proof, "proof_state": "unknown"})
                unknown_rows.append({"sku": sku, **proof})

        row_count = str(len(active_skus))
        if not trace_rows and not active_skus:
            status = "fail"
            value = "floor_source_rows=0"
            root_cause = "H has no floor source rows for the manager to inspect."
        elif active_conflict_no_clean_floor_rows:
            status = "fail"
            sample = ",".join(row["sku"] for row in active_conflict_no_clean_floor_rows[:5])
            value = (
                f"floor_source_rows={len(active_skus)};"
                f"clean_rows={clean_rows};"
                f"fallback_rows={fallback_rows};"
                f"batch_link_proof_needed_rows={batch_link_needed_rows};"
                f"risky_or_unknown_rows={len(risky_rows)};"
                f"unknown_source_rows={len(unknown_rows)};"
                f"token_selection_conflict_no_clean_floor_rows={len(active_conflict_no_clean_floor_rows)};"
                f"sample_skus={sample}"
            )
            root_cause = (
                "H has a token-selection conflict and no clean floor for at least one SKU. "
                "This is an active pricing risk, not parked fallback-cost cleanup."
            )
        elif risky_rows:
            status = "warn"
            sample = ",".join(row["sku"] for row in risky_rows[:5])
            value = (
                f"floor_source_rows={len(active_skus)};"
                f"clean_rows={clean_rows};"
                f"fallback_rows={fallback_rows};"
                f"batch_link_proof_needed_rows={batch_link_needed_rows};"
                f"risky_or_unknown_rows={len(risky_rows)};"
                f"unknown_source_rows={len(unknown_rows)};"
                f"sample_skus={sample}"
            )
            root_cause = (
                "H can calculate the floor, but at least one current floor uses fallback, weak, "
                "unproved, or unknown token cost proof."
            )
        else:
            status = "ok"
            value = (
                f"floor_source_rows={len(active_skus)};"
                f"clean_rows={clean_rows};"
                f"fallback_rows={fallback_rows};"
                f"batch_link_proof_needed_rows={batch_link_needed_rows};"
                "risky_or_unknown_rows=0"
            )
            root_cause = ""
        actual_proof = value

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_token_floor_source_guard",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H floor truth / B token ledger proof",
            expected_output="H floor rows must show whether the chosen token cost source is clean",
            actual_proof=actual_proof,
            row_count=row_count,
            source_path=_h_source(snapshot_path, trace_path, token_ledger_path, audit_path, reconciliation_path),
            summary="H should separate a calculated floor from a cleanly proved floor-cost source.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail or warn, keep the H floor source visible and package the token-source fix separately. "
                "Do not change H prices, token rows, Sheets, or local DB facts from this guard."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_floor_source_active_skus(
    snapshot_rows: list[dict[str, str]] | None,
    trace_rows: list[dict[str, str]],
) -> list[str]:
    skus: list[str] = []
    if snapshot_rows:
        for row in snapshot_rows:
            sku = str(row.get("sku", "") or "").strip().upper()
            if sku:
                skus.append(sku)
    if not skus:
        skus = [str(row.get("sku", "") or "").strip().upper() for row in trace_rows if row.get("sku")]
    out: list[str] = []
    seen = set()
    for sku in skus:
        if not sku or sku in seen:
            continue
        seen.add(sku)
        out.append(sku)
    return out


def _h_latest_trace_rows_by_sku(trace_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_sku: dict[str, tuple[datetime, int, dict[str, str]]] = {}
    for index, row in enumerate(trace_rows):
        sku = str(row.get("sku", "") or "").strip().upper()
        if not sku:
            continue
        parsed = parse_utc(row.get("asof_utc", "")) or datetime.min.replace(tzinfo=timezone.utc)
        current = by_sku.get(sku)
        if current is None or (parsed, index) >= (current[0], current[1]):
            by_sku[sku] = (parsed, index, row)
    return {sku: item[2] for sku, item in by_sku.items()}


def _h_trace_has_token_selection_conflict(trace_row: dict[str, str]) -> bool:
    if str(trace_row.get("token_selection_conflict", "") or "").strip().lower() in {"1", "true", "yes"}:
        return True
    reason_text = ",".join(
        [
            str(trace_row.get("token_selection_conflict_reason", "") or ""),
            str(trace_row.get("reason_codes_csv", "") or ""),
        ]
    ).lower()
    return "token_selection_conflict" in reason_text


def _h_missing_clean_floor(snapshot_row: dict[str, str], trace_row: dict[str, str]) -> bool:
    snapshot_floor = str(
        snapshot_row.get("execution_hard_floor_gbp", "")
        or snapshot_row.get("trace_floor_total_gbp", "")
    ).strip()
    trace_floor = str(trace_row.get("floor_total_gbp", "") or "").strip()
    if not snapshot_floor and not trace_floor:
        return True
    status_text = " ".join(
        [
            str(snapshot_row.get("execution_write_status", "") or ""),
            str(snapshot_row.get("reason_codes_csv", "") or ""),
            str(trace_row.get("reason_codes_csv", "") or ""),
        ]
    ).upper()
    return "FLOOR_INPUT_MISSING_HOLD" in status_text or "H_FLOOR_INPUT_BLOCKED_NO_WRITE" in status_text


def _h_floor_source_proof(
    trace_row: dict[str, str],
    selected_token: dict[str, str],
    audit_by_token: dict[str, dict[str, str]],
    reconciliation_by_token: dict[str, dict[str, str]],
) -> dict[str, str]:
    proof = {
        "proof_state": str(trace_row.get("cogs_source_proof_state", "") or "").strip().lower(),
        "token_id": str(trace_row.get("cogs_source_token_id", "") or "").strip(),
        "token_source": str(trace_row.get("cogs_token_source", "") or "").strip(),
        "source_batch_id": str(trace_row.get("cogs_source_batch_id", "") or "").strip(),
        "source_order_key": str(trace_row.get("cogs_source_order_key", "") or "").strip(),
        "notes": str(trace_row.get("cogs_source_notes", "") or "").strip(),
    }
    if not proof["proof_state"] or proof["proof_state"] == "unknown":
        for key in ("proof_state", "token_id", "token_source", "source_batch_id", "source_order_key", "notes"):
            if selected_token.get(key):
                proof[key] = selected_token.get(key, "")
    proof["is_fallback"] = "1" if _h_is_fallback_cost_source(proof) else "0"
    audit_row = audit_by_token.get(proof.get("token_id", ""))
    if audit_row:
        audit_label = str(audit_row.get("manager_label", "") or "").strip().lower()
        if audit_label == "api_or_receipt_proved":
            proof["proof_state"] = "receipt_proved"
        elif audit_label == "source_token_proved":
            proof["proof_state"] = "source_token_proved"
        elif audit_label == "weak_fallback_cost":
            proof["proof_state"] = "weak_fallback"
        elif audit_label == "not_yet_proven":
            proof["proof_state"] = "unproved"
    reconciliation_row = reconciliation_by_token.get(proof.get("token_id", ""))
    if reconciliation_row:
        rule = str(reconciliation_row.get("reconciliation_rule", "") or "").strip().lower()
        clean_allowed = str(reconciliation_row.get("clean_h_o_trust_allowed", "") or "").strip()
        proof["reconciliation_rule"] = rule
        proof["clean_h_o_trust_allowed"] = clean_allowed
        if clean_allowed != "1" or rule in {"requires_batch_link_proof", "requires_luke_business_decision"}:
            proof["proof_state"] = "batch_link_proof_needed"
    if not proof["proof_state"]:
        proof["proof_state"] = _h_infer_floor_source_proof_state(proof)
    return proof


def _h_selected_token_cost_sources(base: Path) -> tuple[Path | None, dict[str, dict[str, str]]]:
    candidates = [
        base / "out" / "token_ledger_live.csv",
        base / "out" / "systems" / "B" / "live" / "token_ledger_live.csv",
    ]
    token_path = next((path for path in candidates if path.exists()), None)
    if token_path is None:
        return None, {}
    rows = read_csv_dicts(token_path) or []
    usable: list[dict[str, str]] = []
    for row in rows:
        sku = str(row.get("seller_sku", "") or row.get("sku", "") or "").strip().upper()
        cost = _h_money_float(row.get("cost_per_unit", ""))
        if not sku or cost is None or cost <= 0:
            continue
        copied = dict(row)
        copied["_sku_u"] = sku
        usable.append(copied)
    if not usable:
        return token_path, {}
    available = [row for row in usable if str(row.get("status", "") or "").strip().lower() == "available"]
    base_rows = available if available else usable
    selected: dict[str, dict[str, str]] = {}
    for row in sorted(base_rows, key=_h_token_source_sort_key):
        sku = row["_sku_u"]
        if sku in selected:
            continue
        proof = {
            "proof_state": _h_infer_token_row_proof_state(row),
            "token_id": str(row.get("token_id", "") or "").strip(),
            "token_source": str(row.get("source", "") or "").strip(),
            "source_batch_id": str(row.get("source_batch_id", "") or "").strip(),
            "source_order_key": str(row.get("source_order_key", "") or "").strip(),
            "notes": str(row.get("notes", "") or "").strip(),
        }
        proof["is_fallback"] = "1" if _h_is_fallback_cost_source(proof) else "0"
        selected[sku] = proof
    return token_path, selected


def _h_token_source_sort_key(row: dict[str, str]) -> tuple[str, float, datetime, str]:
    rank = _h_money_float(row.get("sort_rank", "") or row.get("lot_rank_num", "") or row.get("lot_rank", ""))
    received = parse_utc(row.get("received_date", "")) or datetime.max.replace(tzinfo=timezone.utc)
    token_id = str(row.get("token_id", "") or "").strip()
    return (row.get("_sku_u", ""), rank if rank is not None else 10**12, received, token_id)


def _h_fallback_cost_audit_by_token(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_dicts(path) or []
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        token_id = str(row.get("token_id", "") or row.get("fallback_token_id", "") or "").strip()
        if token_id:
            out[token_id] = row
    return out


def _h_fallback_cost_reconciliation_by_token(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_dicts(path) or []
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        token_id = str(row.get("token_id", "") or row.get("fallback_token_id", "") or "").strip()
        if token_id:
            out[token_id] = row
    return out


def _h_infer_token_row_proof_state(row: dict[str, str]) -> str:
    proof = {
        "token_id": str(row.get("token_id", "") or "").strip(),
        "token_source": str(row.get("source", "") or "").strip(),
        "notes": str(row.get("notes", "") or "").strip(),
    }
    if not _h_is_fallback_cost_source(proof):
        return "clean"
    cost_source = _h_notes_value(proof["notes"], "cost_source").lower()
    if cost_source == "receipt_proved":
        return "receipt_proved"
    if cost_source == "source_token_proved":
        return "source_token_proved"
    if cost_source:
        return "weak_fallback"
    return "unproved"


def _h_infer_floor_source_proof_state(proof: dict[str, str]) -> str:
    if not proof.get("token_id") and not proof.get("token_source") and not proof.get("notes"):
        return "unknown"
    if not _h_is_fallback_cost_source(proof):
        return "clean"
    cost_source = _h_notes_value(proof.get("notes", ""), "cost_source").lower()
    if cost_source == "receipt_proved":
        return "receipt_proved"
    if cost_source == "source_token_proved":
        return "source_token_proved"
    if cost_source:
        return "weak_fallback"
    return "unproved"


def _h_is_fallback_cost_source(proof: dict[str, str]) -> bool:
    token_id = str(proof.get("token_id", "") or "").strip().upper()
    token_source = str(proof.get("token_source", "") or "").strip().lower()
    notes = str(proof.get("notes", "") or "").strip().lower()
    return (
        token_id.startswith("ADJ-")
        or token_source == "stock_adjustment_fallback"
        or "adjustment_fallback_create:" in notes
    )


def _h_notes_value(notes: object, key: str) -> str:
    wanted = str(key or "").strip().lower()
    for part in str(notes or "").split(";"):
        raw_key, sep, raw_value = part.partition("=")
        if sep and raw_key.strip().lower() == wanted:
            return raw_value.strip()
    return ""


def _h_lock_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    lock_paths = [
        base / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock",
        base / "out" / "H_pricing_cycle.lock",
    ]
    states: list[dict[str, object]] = []
    for path in lock_paths:
        fields = _read_lock_fields(path)
        if not fields:
            continue
        age = _lock_heartbeat_age_seconds(fields, now)
        states.append({"path": path, "fields": fields, "age": age})
    distinct_live: dict[tuple[str, str], dict[str, object]] = {}
    stale_count = 0
    warn_count = 0
    unreadable_count = 0
    for state in states:
        fields = state["fields"]
        if isinstance(fields, dict) and fields.get("_read_error") == "1":
            unreadable_count += 1
            continue
        age = state["age"]
        key = (str(fields.get("pid", "")), _h_norm_run_id(fields.get("run_id", "")))
        if age is None or age >= H_HEARTBEAT_FAIL_SECONDS:
            stale_count += 1
        elif age >= H_HEARTBEAT_WARN_SECONDS:
            warn_count += 1
            distinct_live[key] = state
        else:
            distinct_live[key] = state
    if unreadable_count:
        status = "fail"
        value = f"unreadable_locks={unreadable_count}"
        root_cause = "H lock proof exists but cannot be read."
    elif stale_count:
        status = "fail"
        value = f"stale_or_dead_locks={stale_count};lock_files={len(states)}"
        root_cause = "H lock proof is stale or has no parseable heartbeat."
    elif len(distinct_live) > 1:
        status = "fail"
        value = f"duplicate_h_owners={len(distinct_live)}"
        root_cause = "More than one distinct fresh H owner is visible."
    elif warn_count:
        status = "warn"
        value = f"old_h_heartbeat_locks={warn_count};lock_files={len(states)}"
        root_cause = "H owner heartbeat is getting old."
    elif states:
        status = "ok"
        value = f"fresh_h_owner_locks={len(states)};distinct_owners={len(distinct_live)}"
        root_cause = ""
    else:
        status = "ok"
        value = "no_lock_found"
        root_cause = ""
    details = []
    for state in states:
        fields = state["fields"]
        age = state["age"]
        if isinstance(fields, dict):
            details.append(
                f"{Path(state['path']).name}:pid={fields.get('pid', '')};"
                f"run_id={fields.get('run_id', '')};heartbeat_age_seconds={_seconds_text(age if isinstance(age, float) else None)}"
            )
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_lock_and_heartbeat_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H lock/heartbeat",
            expected_output="one fresh H owner or clean no-owner boundary",
            actual_proof="|".join(details) if details else "no_lock_found",
            source_path=_h_source(*lock_paths),
            summary="H ownership must be single, fresh, and readable.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, package a bounded H ownership-proof task. "
                "Do not clear locks, pause scheduler ownership, or restart workers from MOT."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_boundary_finalizer_rows(
    *,
    base: Path,
    observed_utc: str,
    manifest: dict[str, Any],
    manifest_path: Path | None,
    terminal: dict[str, str],
    terminal_path: Path,
) -> list[dict[str, str]]:
    manifest_state = _h_state(manifest.get("final_state", ""))
    terminal_state = _h_state(terminal.get("state", ""))
    step_notes = ""
    steps = manifest.get("steps", [])
    if isinstance(steps, list) and steps:
        first_step = steps[-1] if isinstance(steps[-1], dict) else {}
        step_notes = str(first_step.get("notes", "") or "")
    failure_code = str(terminal.get("failure_code", "") or "").strip()
    failure_detail = str(terminal.get("failure_detail", "") or "").strip()
    if not manifest_path or not terminal:
        status = "fail"
        value = "boundary_proof_missing"
        root_cause = "H manifest or terminal proof is missing, so finalizer truth is not inspectable."
    elif manifest_state in H_FAIL_STATES:
        status = "fail"
        value = f"manifest_final_state={manifest_state}"
        root_cause = "H manifest finalizer state is failed."
    elif terminal_state not in {"finalized", "finalised"}:
        status = "fail"
        value = f"terminal_state={terminal_state or 'blank'}"
        root_cause = "H terminal proof does not show a finalized boundary."
    elif failure_code or failure_detail:
        status = "fail"
        value = f"failure_code={failure_code or 'blank'}"
        root_cause = "H finalizer proof still carries failure detail."
    elif "LOOP_RC_1" in step_notes and "cause_code=" not in step_notes:
        status = "fail"
        value = "generic_failure_without_cause"
        root_cause = "H manifest reduced the finalizer issue to a generic failure code."
    elif manifest_state not in H_SUCCESS_STATES:
        status = "fail"
        value = f"manifest_final_state={manifest_state or 'blank'}"
        root_cause = "H manifest finalizer state is ambiguous."
    else:
        status = "ok"
        value = f"manifest_final_state={manifest_state};terminal_state={terminal_state}"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_boundary_finalizer_truth",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H guarded finalizer",
            expected_output="clear H finalized or parked boundary truth",
            actual_proof=value,
            source_path=_h_source(manifest_path or (base / "out" / "manifests" / "H"), terminal_path),
            summary="H boundary/finalizer proof must explain whether H safely finished or parked.",
            root_cause_guess=root_cause,
            manager_action="If fail, create a bounded H finalizer-proof task. Do not run H from MOT.",
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_health_clue_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "cycle_alerts" / "checklist_H.csv"
    rows = read_csv_dicts(path)
    if rows is None:
        status = "warn"
        value = "old_checklist_missing"
        root_cause = "Old H checklist is missing; this is only a clue, not final manager truth."
        row_count = ""
    else:
        fail_count = sum(1 for row in rows if str(row.get("status", "")).strip().lower() == "fail")
        warn_count = sum(1 for row in rows if str(row.get("status", "")).strip().lower() == "warn")
        row_count = str(len(rows))
        value = f"old_fail_count={fail_count};old_warn_count={warn_count};rows={len(rows)}"
        if fail_count or warn_count:
            status = "warn"
            root_cause = "Old H checklist has alert clues; newer H MOT proof remains the manager truth."
        else:
            status = "ok"
            root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_health_snapshot_as_clue",
            status=status,
            severity=_severity(status),
            value=value,
            producer="A015 H profile / old checklist",
            expected_output="old checklist read only as supporting clue",
            actual_proof=value,
            row_count=row_count,
            source_path=str(path),
            summary="Old H checklist evidence is a clue only; it does not override newer MOT proof.",
            root_cause_guess=root_cause,
            manager_action="Keep this as H triage context only. Do not repair H from this row alone.",
            safe_repair_boundary="H checklist clue only; no H run, price change, publish, or scheduler ownership change.",
        )
    ]


def _h_storage_cleanup_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    ledger_path = base / "out" / "systems" / "H" / "live" / "H_cleanup_ledger.jsonl"
    staged_path = base / "out" / "systems" / "H" / "staged"
    registry_rule, registry_path, registry_error = _h_storage_registry_rule(base)
    registry_cap = _h_storage_registry_cap(registry_rule)
    ledger_entry, ledger_error = _h_cleanup_ledger_entry(ledger_path)
    ledger_cap = _h_count_cap_from_reason(ledger_entry.get("reason", ""))
    ledger_status = _h_state(ledger_entry.get("status", ""))
    staged_count, staged_dir_count, newest_staged, staged_error = _h_staged_snapshot_state(staged_path)
    newest_preserved = bool(newest_staged)

    registry_cap_text = str(registry_cap) if registry_cap is not None else "missing"
    ledger_cap_text = str(ledger_cap) if ledger_cap is not None else "missing"
    newest_flag = "1" if newest_preserved else "0"
    value = (
        f"cleanup_ledger_present;staged_entries={staged_count};registry_cap={registry_cap_text};"
        f"ledger_count_cap={ledger_cap_text};newest_preserved={newest_flag}"
    )
    actual = (
        f"{value};staged_dirs={staged_dir_count};latest_ledger_status={ledger_status or 'missing'};"
        f"latest_ledger_policy={ledger_entry.get('policy', '')};newest_sample={','.join(newest_staged)}"
    )
    manager_action = (
        "If fail, package a bounded H storage-proof task. "
        "Do not delete outputs from MOT."
    )

    if ledger_error == "cleanup_ledger_missing":
        status = "fail"
        value = "cleanup_ledger_missing"
        root_cause = "H cleanup proof is missing, so rollback preservation is not manager-proven."
        actual = value
    elif ledger_error == "cleanup_ledger_unreadable":
        status = "fail"
        value = "cleanup_ledger_unreadable"
        root_cause = "H cleanup proof is unreadable, so rollback preservation is not manager-proven."
        actual = value
    elif staged_error:
        status = "fail"
        value = staged_error
        root_cause = "H staged rollback folder cannot be inspected, so newest rollback safety is not manager-proven."
        actual = value
    elif registry_error or registry_cap is None:
        status = "fail"
        value = f"{registry_error or 'registry_cap_missing'};staged_entries={staged_count}"
        root_cause = "The central H storage rule is missing or unreadable, so the manager cannot compare cleanup proof."
        actual = value
    elif not newest_preserved:
        status = "fail"
        value = f"newest_rollback_not_proven;staged_entries={staged_count};registry_cap={registry_cap}"
        root_cause = "No staged rollback snapshot folder is readable, so newest rollback safety is not manager-proven."
        actual = value
    elif ledger_status and ledger_status not in H_SUCCESS_STATES:
        status = "fail"
        value = f"cleanup_ledger_status={ledger_status};staged_entries={staged_count};registry_cap={registry_cap}"
        root_cause = "The latest H staged cleanup receipt is not clean."
        actual = value
    elif staged_count > registry_cap:
        status = "warn"
        if ledger_cap is not None and ledger_cap != registry_cap:
            root_cause = "The manager storage rule and H runtime cleanup receipt disagree on the staged rollback cap."
        else:
            root_cause = "H staged rollback count is above the central manager cap, but newest rollback snapshots are present."
        manager_action = (
            "Keep this as warning-only proof and use a separate H source-repair packet if cleanup policy alignment is needed. "
            "Do not delete outputs from MOT."
        )
    elif ledger_error == "staged_cleanup_receipt_missing":
        status = "warn"
        root_cause = "The cleanup ledger is readable, but it does not show an H staged-retention receipt."
    elif ledger_cap is None:
        status = "warn"
        root_cause = "The H staged cleanup receipt is readable, but it does not state its count cap."
    elif ledger_cap != registry_cap:
        status = "warn"
        root_cause = "The H cleanup receipt count cap differs from the central manager storage cap."
        manager_action = (
            "Keep this as warning-only proof and use a separate H source-repair packet if cleanup policy alignment is needed. "
            "Do not delete outputs from MOT."
        )
    else:
        status = "ok"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_storage_cleanup_safety",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H cleanup ledger / storage registry",
            expected_output="cleanup proof exists, matches the central rollback cap, and preserves newest staged snapshots",
            actual_proof=actual,
            row_count=str(staged_count),
            source_path=_h_source(ledger_path, staged_path, registry_path),
            summary="H cleanup proof must protect rollback snapshots and avoid live-output deletion risk.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_reliability_window_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    manifest_root = base / "out" / "manifests" / "H"
    records = _h_recent_manifest_records(manifest_root, limit=H_RELIABILITY_WINDOW_SIZE)
    clean_runs = 0
    warned_runs = 0
    failed_runs = 0
    details: list[str] = []
    source_paths: list[Path] = []
    for record in records:
        source_paths.append(record["path"])
        classification, detail = _h_manifest_reliability_classification(record)
        details.append(detail)
        if classification == "clean":
            clean_runs += 1
        elif classification == "warn":
            warned_runs += 1
        else:
            failed_runs += 1
    inspected_runs = len(records)
    value = (
        f"window_runs={inspected_runs};clean_runs={clean_runs};warned_runs={warned_runs};"
        f"failed_runs={failed_runs};target_clean_runs={H_RELIABILITY_CLEAN_TARGET}"
    )
    if not records:
        status = "fail"
        root_cause = "No H manifests are available for the manager reliability window."
    elif failed_runs:
        status = "fail"
        root_cause = "At least one recent H manifest in the reliability window failed or is ambiguous."
    elif inspected_runs < H_RELIABILITY_WINDOW_SIZE:
        status = "warn"
        root_cause = "H has fewer than 10 comparable completed-run receipts, so stability remains provisional."
    elif clean_runs < H_RELIABILITY_CLEAN_TARGET:
        status = "warn"
        root_cause = "H has enough run receipts, but too many are warning-quality for stable sign-off."
    else:
        status = "ok"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_reliability_window",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H manifest reliability window",
            expected_output="last 10 completed H runs classified as clean, warning, or failed from outside proof",
            actual_proof="|".join(details),
            row_count=str(inspected_runs),
            source_path=_h_source(*(source_paths or [manifest_root])),
            summary="H stability should be based on a recent run window, not only the latest run.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, package the exact failed or ambiguous H run proof. "
                "If warn, keep H provisional until the window is clean enough."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_recent_manifest_records(manifest_root: Path, *, limit: int) -> list[dict[str, Any]]:
    if not manifest_root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in _h_recent_manifest_candidate_paths(manifest_root, limit=limit):
        try:
            text = path.read_text(encoding="utf-8")
            manifest = json.loads(text)
            read_error = ""
        except (OSError, json.JSONDecodeError) as exc:
            manifest = {}
            read_error = exc.__class__.__name__
        records.append(
            {
                "path": path,
                "manifest": manifest if isinstance(manifest, dict) else {},
                "read_error": read_error,
                "sort_time": _h_manifest_sort_time(path, manifest if isinstance(manifest, dict) else {}),
            }
        )
    return sorted(records, key=lambda item: (item["sort_time"], str(item["path"])), reverse=True)[:limit]


def _h_recent_manifest_candidate_paths(manifest_root: Path, *, limit: int) -> list[Path]:
    max_candidates = max(limit * 3, limit)
    candidates: list[Path] = []
    dated_dirs: list[Path] = []
    root_files: list[Path] = []
    try:
        children = list(manifest_root.iterdir())
    except OSError:
        return []
    for child in children:
        if child.is_dir():
            dated_dirs.append(child)
        elif child.suffix.lower() == ".json":
            root_files.append(child)
    for folder in sorted(dated_dirs, key=lambda item: item.name, reverse=True):
        try:
            folder_files = [path for path in folder.iterdir() if path.suffix.lower() == ".json"]
        except OSError:
            continue
        candidates.extend(sorted(folder_files, key=lambda item: item.name, reverse=True))
        if len(candidates) >= max_candidates:
            break
    candidates.extend(sorted(root_files, key=lambda item: item.name, reverse=True))
    return candidates[:max_candidates]


def _h_manifest_sort_time(path: Path, manifest: dict[str, Any]) -> datetime:
    for field in ("end_time", "start_time", "utc"):
        parsed = parse_utc(str(manifest.get(field, "")))
        if parsed is not None:
            return parsed
    parsed_run = _h_parse_run_timestamp(manifest.get("run_id", "") or path.stem)
    if parsed_run is not None:
        return parsed_run
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _h_parse_run_timestamp(value: object) -> datetime | None:
    text = _h_norm_run_id(value)
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _h_manifest_reliability_classification(record: dict[str, Any]) -> tuple[str, str]:
    path = record["path"]
    manifest = record.get("manifest") if isinstance(record.get("manifest"), dict) else {}
    read_error = str(record.get("read_error", "") or "")
    run_id = str(manifest.get("run_id", "") or path.stem)
    if read_error:
        return "fail", f"{run_id}:unreadable:{read_error}"
    final_state = _h_state(manifest.get("final_state", ""))
    steps = manifest.get("steps", [])
    step_failed = False
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_state = _h_state(step.get("step_status", ""))
            rc = str(step.get("rc", "") or "").strip()
            if step_state in H_FAIL_STATES or (rc and rc not in {"0", "0.0"}):
                step_failed = True
                break
    if final_state in H_FAIL_STATES or step_failed:
        return "fail", f"{run_id}:failed:{final_state or 'blank'}"
    if final_state not in H_SUCCESS_STATES:
        return "fail", f"{run_id}:ambiguous:{final_state or 'blank'}"
    health = manifest.get("health_summary", {})
    fail_count = _safe_int(health.get("fail_count", 0) if isinstance(health, dict) else 0)
    warn_count = _safe_int(health.get("warn_count", 0) if isinstance(health, dict) else 0)
    if fail_count or warn_count:
        return "warn", f"{run_id}:warn:health_fail={fail_count}:health_warn={warn_count}"
    return "clean", f"{run_id}:clean"


def _safe_int(value: object) -> int:
    try:
        return int(float(str(value or "0").strip()))
    except ValueError:
        return 0


def _h_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _h_money_float(value: object) -> float | None:
    try:
        return float(str(value or "").strip())
    except (TypeError, ValueError):
        return None


def _h_defensive_listing_protection_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    config_path = base / "config" / "h_defensive_listing_protection.csv"
    action_path = base / "out" / "h_defensive_listing_action_log.csv"
    memory_path = base / "out" / "h_defensive_listing_campaign_memory.csv"
    daily_path = base / "out" / "h_defensive_listing_daily.csv"
    config_rows = read_csv_dicts(config_path)
    action_rows = read_csv_rows(action_path)
    daily_rows = read_csv_rows(daily_path)
    source_path = _h_source(config_path, action_path, memory_path, daily_path)

    if config_rows is None:
        status = "ok"
        value = "not_configured"
        actual = "no defensive listing config"
        root_cause = ""
    else:
        enabled_rows = [row for row in config_rows if _h_bool(row.get("enabled", ""))]
        allowed_modes = {"pressure_then_match", "match_only", "off", "balanced_defend"}
        invalid_rows = [
            row
            for row in enabled_rows
            if not str(row.get("sku", "")).strip()
            or not str(row.get("asin", "")).strip()
            or str(row.get("mode", "")).strip().lower() not in allowed_modes
        ]
        live_rows = [row for row in enabled_rows if _h_bool(row.get("live_write_enabled", ""))]
        non_allowlisted_live = [
            row for row in live_rows if str(row.get("sku", "")).strip() != "6V-EEC1-2S9Z"
        ]
        applied_while_preview = [
            row
            for row in action_rows
            if row.get("write_status") == "APPLIED" and row.get("live_write_enabled") != "1"
        ]
        proof_missing_live = bool(live_rows and not action_rows and not daily_rows)
        proof_rows_missing_floor_ceiling = [
            row
            for row in action_rows
            if row.get("write_required") == "1"
            and (not row.get("hard_floor_gbp") or not row.get("final_ceiling_gbp"))
        ]
        b06_proof_rows = [
            row
            for row in action_rows
            if row.get("sku") == "6V-EEC1-2S9Z" or row.get("asin") == "B06WW79DX5"
        ]
        latest_b06_proof = b06_proof_rows[-1] if b06_proof_rows else {}
        historical_strategy_ownership_violation_rows = []
        latest_strategy_ownership_violation = False
        for row in b06_proof_rows:
            rival = _h_money_float(row.get("lowest_rival_price_gbp"))
            target = _h_money_float(row.get("target_price_gbp"))
            phase = str(row.get("phase", "") or "").strip()
            write_status = str(row.get("write_status", "") or "").strip()
            violation = False
            if rival is not None and phase in {"daily_write_limit", "normal_h_control"}:
                violation = True
            elif rival is not None and write_status == "DEFENSIVE_NOT_TRIGGERED_NORMAL_H_CONTROL":
                violation = True
            elif write_status == "APPLIED":
                if target is None or rival is None:
                    violation = True
                elif phase in {"pressure_undercut", "balanced_defend"} and target >= rival:
                    violation = True
                elif phase == "pressure_hold":
                    violation = True
            if violation:
                if row is latest_b06_proof:
                    latest_strategy_ownership_violation = True
                else:
                    historical_strategy_ownership_violation_rows.append(row)

        if invalid_rows:
            status = "fail"
            value = f"invalid_enabled_rows={len(invalid_rows)}"
            root_cause = "Defensive listing config has enabled rows without the minimum safe fields."
        elif non_allowlisted_live:
            status = "fail"
            value = f"non_allowlisted_live_rows={len(non_allowlisted_live)}"
            root_cause = "A defensive listing live-write row is enabled outside the protected one-SKU allowlist."
        elif applied_while_preview:
            status = "fail"
            value = f"applied_while_preview_rows={len(applied_while_preview)}"
            root_cause = "A defensive listing action was applied even though the proof row says live writes were disabled."
        elif proof_rows_missing_floor_ceiling:
            status = "fail"
            value = f"write_rows_missing_floor_or_ceiling={len(proof_rows_missing_floor_ceiling)}"
            root_cause = "A defensive listing write-required proof row lacks floor or ceiling evidence."
        elif latest_strategy_ownership_violation:
            status = "fail"
            value = (
                "latest_strategy_ownership_violation=1;"
                f"latest_b06_write_status={latest_b06_proof.get('write_status', '')};"
                f"latest_b06_phase={latest_b06_proof.get('phase', '')};"
                f"latest_b06_current={latest_b06_proof.get('current_price_gbp', '')};"
                f"latest_b06_rival={latest_b06_proof.get('lowest_rival_price_gbp', '')}"
            )
            root_cause = "The latest B06 defensive listing proof row shows strategy ownership leaking back to normal H or using an invalid defensive target."
        elif proof_missing_live:
            status = "warn"
            value = f"live_enabled_waiting_proof;enabled_rows={len(enabled_rows)}"
            root_cause = "Defensive listing live mode is enabled but no proof row has been seen yet."
        elif enabled_rows:
            preview_count = sum(1 for row in enabled_rows if not _h_bool(row.get("live_write_enabled", "")))
            status = "ok"
            value = (
                f"enabled_rows={len(enabled_rows)};preview_rows={preview_count};"
                f"live_rows={len(live_rows)};proof_rows={len(action_rows)};daily_rows={len(daily_rows)}"
            )
            root_cause = ""
        else:
            status = "ok"
            value = f"configured_disabled;rows={len(config_rows)}"
            root_cause = ""
        actual = (
            f"config_rows={0 if config_rows is None else len(config_rows)};"
            f"action_rows={len(action_rows)};daily_rows={len(daily_rows)};"
            f"b06_proof_rows={len(b06_proof_rows)};"
            f"latest_b06_status={latest_b06_proof.get('write_status', '')};"
            f"latest_b06_current={latest_b06_proof.get('current_price_gbp', '')};"
            f"latest_b06_rival={latest_b06_proof.get('lowest_rival_price_gbp', '')};"
            f"latest_b06_target={latest_b06_proof.get('target_price_gbp', '')};"
            f"historical_strategy_ownership_violation_rows={len(historical_strategy_ownership_violation_rows)}"
        )

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_defensive_listing_protection_mode",
            status=status,
            severity=_severity(status),
            value=value,
            producer="phase1_defensive_listing / H MOT",
            expected_output="defensive listing config and proof are readable, preview-safe, and floor/ceiling-gated",
            actual_proof=actual,
            row_count=str(len(action_rows)),
            source_path=source_path,
            summary="H defensive listing protection must be opt-in, visible, and locked before live price writes.",
            root_cause_guess=root_cause,
            manager_action=(
                "If warn or fail, package a bounded H defensive-listing proof task. "
                "Do not change prices or enable live writes from MOT."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _h_manager_readiness_rows(*, rows: list[dict[str, str]], observed_utc: str) -> list[dict[str, str]]:
    ignored = {"h_health_snapshot_as_clue", "h_manager_readiness"}
    core_rows = [row for row in rows if row.get("check") not in ignored]
    failed = [row for row in core_rows if row.get("status") == "fail"]
    warned = [row for row in core_rows if row.get("status") == "warn"]
    if failed:
        status = "fail"
        value = f"not_ready;failed_checks={len(failed)}"
        root_cause = "H is not independently manager-proven from outside evidence."
    elif warned:
        status = "warn"
        value = f"ready_with_warnings;warn_checks={len(warned)}"
        root_cause = "H is inspectable but has non-blocking manager warnings."
    else:
        status = "ok"
        value = "manager_readable"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="H",
            check="h_manager_readiness",
            status=status,
            severity=_severity(status),
            value=value,
            producer="sellerone_manager.hourly_mot",
            expected_output="H can be explained from independent read-only proof",
            actual_proof=value,
            summary="The manager should only call H ready when outside proof is readable and non-contradictory.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, keep H parked and create bounded proof tasks. "
                "First build the H manager/MOT layer, then repairs become controlled."
            ),
            safe_repair_boundary=H_PROOF_ONLY_BOUNDARY,
        )
    ]


def _file_status_for_age(path: Path, now: datetime, *, warn_hours: float, fail_hours: float) -> tuple[str, float | None]:
    age = file_age_hours(path, now)
    return status_from_age(age, warn_hours=warn_hours, fail_hours=fail_hours), age


def _f_manager_snapshot_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "M" / "f_price_list_manager_snapshot.csv"
    rows = read_csv_rows(path)
    f_rows = [row for row in rows if str(row.get("flow", "")).upper() == "F"] or rows
    latest = _latest_csv_row(f_rows)
    age_status, age = _file_status_for_age(path, now, warn_hours=F_MANAGER_WARN_HOURS, fail_hours=F_MANAGER_FAIL_HOURS)
    snapshot_status = str(latest.get("status", "")).strip().lower()
    known_statuses = {"ok", "warn", "blocked", "fail", "needs_user", "stale_evidence"}

    if not path.exists() or not rows:
        status = "fail"
        value = "missing"
        root_cause = "The F manager snapshot is missing or empty."
        manager_action = "Create a manager-only repair task to restore the F snapshot writer. Do not run F061."
    elif snapshot_status not in known_statuses:
        status = "warn"
        value = snapshot_status or "blank"
        root_cause = "The F manager snapshot has an unclassified status."
        manager_action = "Classify the F manager state before making any scanner decision."
    elif snapshot_status == "needs_user" or str(latest.get("needs_user", "")) == "1":
        status = "decision_needed"
        value = snapshot_status
        root_cause = str(latest.get("active_blocker_summary", "")) or "F manager says a human decision is needed."
        manager_action = str(latest.get("user_action", "")) or "Keep the affected F row parked until Luke decides."
    elif snapshot_status in {"fail", "blocked"}:
        status = "fail"
        value = snapshot_status
        root_cause = str(latest.get("active_blocker_summary", "")) or "F manager snapshot reports an active blocker."
        manager_action = "Create a bounded manager task for the F proof gap. Do not repair the scanner from MOT."
    elif snapshot_status == "stale_evidence":
        status = "warn"
        value = snapshot_status
        root_cause = str(latest.get("active_blocker_summary", "")) or "F manager snapshot says evidence is stale."
        manager_action = "Wait for the manager-owned refresh or plan a separate safe proof window."
    else:
        status = age_status
        value = snapshot_status
        root_cause = "The F manager snapshot is stale." if status != "ok" else ""
        manager_action = "Refresh the read-only manager front door. Do not run F061." if status != "ok" else "No action; manager snapshot is readable."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_manager_snapshot_current",
            status=status,
            severity=_severity(status),
            value=value,
            producer="sellerone_manager.f_price_list_snapshot",
            expected_output="out/systems/M/f_price_list_manager_snapshot.csv",
            actual_proof=(
                f"exists={1 if path.exists() else 0};rows={len(rows)};age_hours={_age_text(age)};"
                f"snapshot_status={snapshot_status};supplier={latest.get('queue_supplier_id', '')}"
            ),
            age_hours=_age_text(age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(path),
            summary="F manager snapshot exists and gives an understandable outside status.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if status == "decision_needed" else "0",
            safe_repair_boundary="Manager snapshot proof only; no F061 run, queue edit, handoff approval, or scanner repair.",
        )
    ]


def _f_latest_live_status(base: Path) -> tuple[Path, list[dict[str, str]], dict[str, str]]:
    path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_status.csv"
    rows = read_csv_rows(path)
    return path, rows, _latest_csv_row(rows)


def _field_age_seconds(fields: dict[str, str], now: datetime, *names: str) -> float | None:
    for name in names:
        parsed = parse_utc(fields.get(name, ""))
        if parsed is not None:
            return max((now - parsed).total_seconds(), 0.0)
    return None


def _optional_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _f_latest_scanner_progress_age(base: Path, now: datetime) -> tuple[float | None, str]:
    events_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv"
    latest = None
    latest_raw = ""
    for row in read_csv_rows(events_path):
        if str(row.get("event_type", "")).strip().lower() != "scanner_chunk":
            continue
        status = str(row.get("status", "")).strip().lower()
        if status and status != "success":
            continue
        raw = str(row.get("event_utc", "") or row.get("observed_utc", "")).strip()
        parsed = parse_utc(raw)
        if parsed is None:
            continue
        if latest is None or parsed > latest:
            latest = parsed
            latest_raw = raw
    if latest is None:
        return None, ""
    return max((now - latest).total_seconds(), 0.0), latest_raw


def _f_note_int(notes: object, field_name: str) -> int | None:
    match = re.search(rf"(?:^|[;|,\s]){re.escape(field_name)}=(-?\d+)", str(notes or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _f_plain_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        return int(float(text)) if text else 0
    except (TypeError, ValueError):
        return 0


def _f_recent_scanner_stall(base: Path, live: dict[str, str]) -> dict[str, str]:
    active_supplier = str(live.get("active_supplier_id", "")).strip().lower()
    if not active_supplier:
        return {"state": "not_checked", "active_supplier_id": ""}

    events_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv"
    scanner_rows: list[dict[str, object]] = []
    memory_block_rows: list[datetime] = []
    for row in read_csv_rows(events_path):
        supplier_id = str(row.get("supplier_id", "")).strip().lower()
        if supplier_id != active_supplier:
            continue
        parsed = parse_utc(str(row.get("event_utc", "") or row.get("observed_utc", "")))
        if parsed is None:
            continue
        event_type = str(row.get("event_type", "")).strip().lower()
        status = str(row.get("status", "")).strip().lower()
        if event_type == "scanner_chunk" and (not status or status == "success"):
            pending_after = _f_note_int(row.get("notes", ""), "pending_after")
            if pending_after is None:
                continue
            scanner_rows.append(
                {
                    "event_utc": parsed,
                    "pending_after": pending_after,
                    "processed_rows": _f_plain_int(row.get("rows", "")),
                }
            )
        elif event_type == "f061_memory_import" and status in {"blocked", "failed", "error"}:
            memory_block_rows.append(parsed)

    scanner_rows.sort(key=lambda item: item["event_utc"])
    if len(scanner_rows) < F_PROGRESS_STALL_MIN_CHUNKS:
        return {
            "state": "insufficient_history",
            "active_supplier_id": active_supplier,
            "recent_scanner_chunks": str(len(scanner_rows)),
            "events_exists": "1" if events_path.exists() else "0",
        }

    recent = scanner_rows[-F_PROGRESS_STALL_MIN_CHUNKS:]
    first_time = recent[0]["event_utc"]
    latest_time = recent[-1]["event_utc"]
    assert isinstance(first_time, datetime)
    assert isinstance(latest_time, datetime)
    first_pending = int(recent[0]["pending_after"])
    latest_pending = int(recent[-1]["pending_after"])
    pending_drop = first_pending - latest_pending
    processed_total = sum(int(item["processed_rows"]) for item in recent)
    span_minutes = max((latest_time - first_time).total_seconds() / 60.0, 0.0)
    memory_block_recent = sum(1 for item in memory_block_rows if item >= first_time)
    stalled = (
        latest_pending > 0
        and span_minutes >= F_PROGRESS_STALL_MIN_MINUTES
        and pending_drop <= F_PROGRESS_STALL_MAX_PENDING_DROP
        and processed_total > 0
    )
    return {
        "state": "stalled" if stalled else "progressing",
        "active_supplier_id": active_supplier,
        "recent_scanner_chunks": str(len(recent)),
        "span_minutes": f"{span_minutes:.1f}",
        "first_pending_after": str(first_pending),
        "latest_pending_after": str(latest_pending),
        "pending_drop": str(pending_drop),
        "processed_rows": str(processed_total),
        "memory_import_blocked_recent": str(memory_block_recent),
        "events_exists": "1" if events_path.exists() else "0",
    }


def _f_live_owner_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    live_path, live_rows, live = _f_latest_live_status(base)
    supervisor_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "fpm_live_supervisor_state.txt"
    supervisor = _read_lock_fields(supervisor_path)
    live_age_status, live_age = _file_status_for_age(live_path, now, warn_hours=F_LIVE_WARN_HOURS, fail_hours=F_LIVE_FAIL_HOURS)
    supervisor_age = _field_age_seconds(supervisor, now, "updated_utc")
    state = str(live.get("state", "")).strip().lower()
    supervisor_state = str(supervisor.get("state", "")).strip().lower()
    supervisor_progress_state = str(supervisor.get("progress_state", "")).strip().lower()
    supervisor_scanner_progress_age = _optional_float(supervisor.get("scanner_progress_age_seconds", ""))
    event_scanner_progress_age, event_scanner_progress_utc = _f_latest_scanner_progress_age(base, now)
    scanner_progress_age = supervisor_scanner_progress_age
    scanner_progress_source = "supervisor"
    if scanner_progress_age is None:
        scanner_progress_age = event_scanner_progress_age
        scanner_progress_source = "events" if event_scanner_progress_age is not None else ""
    supervisor_stale_seconds = _optional_float(supervisor.get("stale_seconds", "")) or 900.0
    scanner_stall = _f_recent_scanner_stall(base, live) if live_path.exists() and live_rows else {"state": "not_checked"}
    luke_action_required = "0"
    heartbeat_progress_states = {"known_wait", "scanner_alive_inside_batch"}

    if not live_path.exists() or not live_rows:
        status = "fail"
        value = "missing"
        root_cause = "The live F owner status is missing or empty."
        manager_action = "Restore live owner status evidence before queue or scanner decisions. Do not restart workers from MOT."
    elif state == "blocked_source_shape_guard":
        status = "decision_needed"
        value = state
        root_cause = str(live.get("notes", "")) or "The live F owner is blocked by active source-row shape proof."
        manager_action = (
            "Needs protected decision: approve a bounded F source-shape recovery preview for the active row, "
            "or leave F parked. Do not edit active rows from MOT."
        )
        luke_action_required = "1"
    elif state in {"blocked", "failed", "error"} or state.startswith("blocked_"):
        status = "fail"
        value = state
        root_cause = str(live.get("notes", "")) or "The live F owner reports a blocked or failed state."
        manager_action = "Create a manager-approved F task to classify the live blocker before touching the scanner."
    elif state not in {"running", "idle", "completed", "drain_wait"}:
        status = "warn"
        value = state or "blank"
        root_cause = "The live F owner state is not classified by the MOT."
        manager_action = "Classify this F owner state in manager code before changing worker behavior."
    elif live_age_status == "fail":
        status = "fail"
        value = state
        root_cause = "The live F owner status file is stale."
        manager_action = "Treat F as stuck until owner proof refreshes. Do not restart workers from MOT."
    elif state == "running" and scanner_stall.get("state") == "stalled":
        status = "fail"
        value = f"{state}/supplier_progress_stalled"
        root_cause = (
            "The F scanner is alive, but repeated active-supplier chunks are not reducing pending work. "
            "This is an alive-but-stuck scanner loop, not clean progress."
        )
        manager_action = (
            "Create a bounded F scanner forward-progress repair packet for the active supplier. "
            "Do not restart F, switch suppliers, edit the queue, or rewrite outputs from MOT."
        )
    elif supervisor_path.exists() and supervisor_state == "alive_no_progress":
        status = "warn"
        value = f"{state}/alive_no_progress"
        root_cause = "The F process is alive, but recent scanner row progress is not proven."
        manager_action = "Keep F visible as alive-but-not-moving; package scanner progress repair if this persists."
    elif (
        supervisor_path.exists()
        and state == "running"
        and (
            supervisor_state in {"alive_inside_batch", "waiting_known_action"}
            or supervisor_progress_state in heartbeat_progress_states
        )
    ):
        status = "ok"
        value = f"{state}/{supervisor_progress_state or supervisor_state}"
        root_cause = ""
        manager_action = "No action; F has fresh in-batch scanner heartbeat proof."
    elif (
        supervisor_path.exists()
        and state == "running"
        and supervisor_state in {"ok", "idle", "running", "completed"}
        and scanner_progress_age is not None
        and scanner_progress_age > supervisor_stale_seconds
    ):
        status = "warn"
        value = f"{state}/no_recent_scanner_progress"
        root_cause = "The F process proof is fresh, but the last scanner chunk is stale."
        manager_action = "Treat the UI heartbeat as process-only proof; inspect scanner progress before trusting catch-up wording."
    elif supervisor_path.exists() and supervisor_state not in {
        "ok",
        "idle",
        "running",
        "completed",
        "alive_inside_batch",
        "waiting_known_action",
    }:
        status = "fail"
        value = f"{state}/{supervisor_state or 'blank'}"
        root_cause = "Live owner status and supervisor state disagree."
        manager_action = "Create a bounded F manager task to classify ownership evidence."
    elif not supervisor_path.exists() and state == "running":
        status = "fail"
        value = f"{state}/missing_supervisor"
        root_cause = "F says it is running but supervisor proof is missing."
        manager_action = "Restore supervisor proof before trusting live scanner ownership."
    else:
        status = "warn" if live_age_status == "warn" else "ok"
        value = state
        root_cause = "The live F owner status is getting stale." if status == "warn" else ""
        manager_action = "No action; live owner proof is readable." if status == "ok" else "Watch for the next owner refresh before acting."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_live_owner_status",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM130_run_live_cycle.py / FPM170_supervise_live_cycle.py",
            expected_output="out/systems/F/price_list_manager/live/live_cycle_status.csv",
            actual_proof=(
                f"exists={1 if live_path.exists() else 0};rows={len(live_rows)};age_hours={_age_text(live_age)};"
                f"state={state};supervisor_state={supervisor_state};supervisor_age_seconds={_seconds_text(supervisor_age)};"
                f"progress_state={supervisor_progress_state};"
                f"scanner_progress_age_seconds={_seconds_text(scanner_progress_age)};"
                f"scanner_progress_source={scanner_progress_source};scanner_progress_utc={event_scanner_progress_utc};"
                f"active_supplier_id={scanner_stall.get('active_supplier_id', '')};"
                f"scanner_forward_state={scanner_stall.get('state', '')};"
                f"recent_scanner_chunks={scanner_stall.get('recent_scanner_chunks', '')};"
                f"scanner_span_minutes={scanner_stall.get('span_minutes', '')};"
                f"first_pending_after={scanner_stall.get('first_pending_after', '')};"
                f"latest_pending_after={scanner_stall.get('latest_pending_after', '')};"
                f"pending_drop={scanner_stall.get('pending_drop', '')};"
                f"processed_rows={scanner_stall.get('processed_rows', '')};"
                f"memory_import_blocked_recent={scanner_stall.get('memory_import_blocked_recent', '')}"
            ),
            age_hours=_age_text(live_age),
            row_count=str(len(live_rows)) if live_rows else "",
            source_path=str(live_path),
            summary="F live owner status and supervisor evidence are readable and current.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required=luke_action_required,
            safe_repair_boundary=(
                "F owner and forward-progress proof only; no F061 run, no restart, no queue edit, "
                "no supplier switch, no scanner output rewrite, no Sheet write, and no price change."
            ),
        )
    ]


def _f_child_heartbeat_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    _live_path, _live_rows, live = _f_latest_live_status(base)
    owner_state = str(live.get("state", "")).strip().lower()
    path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_child_status.txt"
    fields = _read_lock_fields(path)
    age_seconds = _field_age_seconds(fields, now, "heartbeat", "last_output_utc", "started")

    inactive_owner_state = owner_state in {"idle", "completed", "drain_wait", "drain_exit", "login_wait"} or owner_state.startswith("blocked_")

    if inactive_owner_state:
        status = "ok"
        value = "owner_not_running"
        root_cause = ""
        manager_action = "No action; F owner is not currently expecting an active scanner child."
    elif not path.exists() and owner_state == "running":
        status = "fail"
        value = "missing"
        root_cause = "F owner says running, but scanner child heartbeat proof is missing."
        manager_action = "Treat scanner state as unsafe until child proof returns. Do not restart from MOT."
    elif not path.exists():
        status = "warn"
        value = "missing"
        root_cause = "Scanner child proof is absent while F is not clearly running."
        manager_action = "Keep this as manager evidence only; do not start scanner work."
    elif age_seconds is None:
        status = "warn"
        value = "unparseable"
        root_cause = "Scanner child heartbeat file exists but does not expose a parseable timestamp."
        manager_action = "Classify the child status format before using it as proof."
    elif owner_state == "running" and age_seconds >= F_CHILD_FAIL_SECONDS:
        status = "fail"
        value = f"{age_seconds:.0f}s"
        root_cause = "F owner says running, but scanner child heartbeat is stale."
        manager_action = "Create a bounded F owner/child proof task. Do not restart workers from MOT."
    elif age_seconds >= F_CHILD_WARN_SECONDS:
        status = "warn"
        value = f"{age_seconds:.0f}s"
        root_cause = "Scanner child heartbeat is older than expected."
        manager_action = "Watch for the next heartbeat before treating F as actively progressing."
    else:
        status = "ok"
        value = f"{age_seconds:.0f}s"
        root_cause = ""
        manager_action = "No action; scanner child heartbeat is fresh."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_child_scanner_heartbeat",
            status=status,
            severity=_severity(status),
            value=value,
            producer="F061 child process status writer",
            expected_output="out/systems/F/price_list_manager/live/f061_child_status.txt",
            actual_proof=(
                f"exists={1 if path.exists() else 0};owner_state={owner_state};"
                f"pid={fields.get('pid', '')};age_seconds={_seconds_text(age_seconds)}"
            ),
            source_path=str(path),
            summary="F child scanner heartbeat matches the live owner state.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Heartbeat proof only; no worker restart, no scanner run, no process kill.",
        )
    ]


def _f_bbp_iframe_plugin_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    live_dir = base / "out" / "systems" / "F" / "price_list_manager" / "live"
    browser_path = live_dir / "f061_browser_visibility_state.txt"
    stderr_path = live_dir / "f061_child_stderr.log"
    browser = _read_lock_fields(browser_path)
    browser_reason = str(browser.get("reason", "")).strip().lower()
    browser_auth_state = str(browser.get("auth_state", "")).strip().lower()
    try:
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace").lower()[-20000:]
    except OSError:
        stderr_text = ""
    tokens = (
        "f061_bbp_profile_health ok=false",
        "buybotpro_extension_missing",
        "bbp_profile_extension_missing",
        "bbp iframe preflight failed",
        "bbp iframe missing, but no real login option was detected",
        "no bbp iframe",
    )
    token_hits = [token for token in tokens if token in stderr_text]
    age_hours = file_age_hours(stderr_path, now)
    if "bbp_iframe_plugin_blocked" in browser_reason or browser_auth_state == "bbp_iframe_plugin_blocked":
        status = "warn"
        value = "state_blocked"
        root_cause = "F says BBP proof is blocked by plugin/iframe availability, not a normal login decision."
        manager_action = "Repair BBP profile/plugin/iframe detection inside F-BBP-IFRAME-STALL. Do not open a separate browser or edit queues."
    elif token_hits:
        status = "warn"
        value = "stderr_blocked"
        root_cause = "The scanner child log shows repeated BBP profile or iframe failure."
        manager_action = "Classify this as BBP iframe/plugin blocked, not normal catch-up or ordinary login."
    else:
        status = "ok"
        value = "no_block_signal"
        root_cause = ""
        manager_action = "No action; BBP iframe/plugin stall proof is not currently visible."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_bbp_iframe_plugin_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="F061_run_legacy_first_checks_local.py / FPM130_run_live_cycle.py",
            expected_output="out/systems/F/price_list_manager/live/f061_child_stderr.log",
            actual_proof=(
                f"stderr_exists={1 if stderr_path.exists() else 0};stderr_age_hours={_age_text(age_hours)};"
                f"browser_reason={browser_reason};browser_auth_state={browser_auth_state};"
                f"token_hits={','.join(token_hits[:3])}"
            ),
            age_hours=_age_text(age_hours),
            source_path=str(stderr_path),
            summary="F BBP iframe/plugin proof should be separate from BBP account login proof.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Read-only BBP iframe/plugin proof; no F061 run, no worker restart, no queue edit, no browser opening.",
        )
    ]


def _f_storage_drift_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "storage_drift_report.csv"
    rows = read_csv_rows(path)
    age_status, age = _file_status_for_age(path, now, warn_hours=24.0, fail_hours=48.0)
    bad_rows: list[dict[str, str]] = []
    for row in rows:
        status_value = str(row.get("status_after") or row.get("status_before") or "").strip().lower()
        delta_text = str(row.get("row_delta_after") or row.get("row_delta_before") or "0").strip()
        try:
            delta = int(float(delta_text or "0"))
        except ValueError:
            delta = 0
        if status_value not in {"ok", ""} or delta != 0:
            bad_rows.append(row)

    if not path.exists() or not rows:
        status = "fail"
        value = "missing"
        root_cause = "F storage drift proof is missing or empty."
        manager_action = "Restore storage drift proof before trusting live F scanner outputs."
    elif bad_rows:
        status = "fail"
        value = str(len(bad_rows))
        root_cause = "At least one F storage contract is not aligned."
        manager_action = "Create a manager-approved storage-drift task. Do not align CSV and SQL from MOT."
    else:
        status = "warn" if age_status == "warn" else "fail" if age_status == "fail" else "ok"
        value = str(len(rows))
        root_cause = "F storage drift proof is stale." if status != "ok" else ""
        manager_action = "Refresh manager-owned drift proof at a safe boundary." if status != "ok" else "No action; storage drift proof is aligned."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_storage_drift_clear",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM129_storage_drift_guard.py",
            expected_output="out/systems/F/price_list_manager/live/storage_drift_report.csv",
            actual_proof=f"exists={1 if path.exists() else 0};rows={len(rows)};bad_rows={len(bad_rows)};age_hours={_age_text(age)}",
            age_hours=_age_text(age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(path),
            summary="F storage drift report shows CSV and SQL-compatible proof are aligned.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Storage proof only; no local DB alignment, CSV rewrite, output deletion, or scanner run.",
        )
    ]


def _f_queue_recommendation_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    dashboard_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv"
    report_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "next_action_report.md"
    rows = read_csv_rows(dashboard_path)
    top = rows[0] if rows else {}
    dashboard_age_status, dashboard_age = _file_status_for_age(
        dashboard_path,
        now,
        warn_hours=F_TEST_MODE_WARN_HOURS,
        fail_hours=F_TEST_MODE_FAIL_HOURS,
    )
    report_age_status, report_age = _file_status_for_age(
        report_path,
        now,
        warn_hours=F_TEST_MODE_WARN_HOURS,
        fail_hours=F_TEST_MODE_FAIL_HOURS,
    )
    queue_state = str(top.get("queue_state", "")).strip()
    supplier = str(top.get("supplier_id", "")).strip()

    if not dashboard_path.exists() or not rows:
        status = "fail"
        value = "missing"
        root_cause = "The F queue dashboard is missing or empty."
        manager_action = "Restore dashboard proof at a safe manager boundary. Do not change queue state."
    elif not supplier or not queue_state:
        status = "fail"
        value = "incomplete"
        root_cause = "The F queue dashboard does not explain the top supplier recommendation."
        manager_action = "Create a manager-only task to repair dashboard proof fields."
    elif "needs manual file" in queue_state.lower():
        status = "decision_needed"
        value = f"{supplier}:{queue_state}"
        root_cause = "The next supplier needs a manual price file before F can continue that path."
        manager_action = f"Supply the missing price file for {top.get('supplier_name', supplier)} through the normal inbox path."
    elif dashboard_age_status == "fail" or report_age_status == "fail":
        status = "fail"
        value = f"{supplier}:{queue_state}"
        root_cause = "F queue recommendation proof is too stale to trust."
        manager_action = "Refresh manager queue proof. Do not run F061 from MOT."
    elif dashboard_age_status == "warn" or report_age_status == "warn" or not report_path.exists():
        status = "warn"
        value = f"{supplier}:{queue_state}"
        root_cause = "F queue recommendation proof is readable but stale or missing the markdown report."
        manager_action = "Refresh manager queue proof at a safe boundary."
    else:
        status = "ok"
        value = f"{supplier}:{queue_state}"
        root_cause = ""
        manager_action = "No action; queue recommendation is explainable."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_queue_recommendation_explainable",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM050_build_next_action_report.py / FPM060_build_status_dashboard.py",
            expected_output="out/systems/F/price_list_manager/test_mode/status_dashboard.csv",
            actual_proof=(
                f"dashboard_exists={1 if dashboard_path.exists() else 0};rows={len(rows)};"
                f"dashboard_age_hours={_age_text(dashboard_age)};report_exists={1 if report_path.exists() else 0};"
                f"report_age_hours={_age_text(report_age)};web_unprocessed={top.get('web_unprocessed', '')}"
            ),
            age_hours=_age_text(dashboard_age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(dashboard_path),
            summary="F queue recommendation has a visible supplier, state, and unprocessed count.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if status == "decision_needed" else "0",
            safe_repair_boundary="Queue proof only; no queue controls, F061 handoff approval, scanner run, or live queue edit.",
        )
    ]


def _mot_text(value: object) -> str:
    return str(value or "").strip()


def _mot_int(value: object) -> int:
    try:
        return int(float(_mot_text(value) or "0"))
    except ValueError:
        return 0


def _existing_path(base: Path, raw: object) -> Path | None:
    text = _mot_text(raw)
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = base / text
    return path if path.exists() else None


def _latest_for_supplier(rows: list[dict[str, str]], supplier_id: str, *, time_field: str) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if _mot_text(row.get("supplier_id", "")).lower() == supplier_id.lower()
    ]
    return _latest_csv_row(matches, time_field=time_field)


def _load_f_gmail_source_config(base: Path) -> dict[str, dict[str, str]]:
    path = base / "secrets" / "price_list_manager" / "gmail_sources.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for supplier_id, values in payload.items():
        if isinstance(values, dict):
            out[_mot_text(supplier_id).lower()] = {
                _mot_text(key): _mot_text(value)
                for key, value in values.items()
            }
    return out


def _expected_f_gmail_label(base: Path, supplier_id: str, supplier_name: str) -> str:
    config = _load_f_gmail_source_config(base).get(supplier_id.lower(), {})
    return (
        _mot_text(config.get("label_name"))
        or F_DEFAULT_GMAIL_LABEL_BY_SUPPLIER.get(supplier_id.lower(), "")
        or supplier_name
        or supplier_id
    )


def _f_active_supplier_rows(base: Path) -> list[dict[str, str]]:
    registry_path = base / "config" / "feeder" / "price_list_manager" / "suppliers.csv"
    rows = read_csv_rows(registry_path)
    out: list[dict[str, str]] = []
    for row in rows:
        active = _mot_text(row.get("active_flag", "")).lower()
        if active in {"", "0", "false", "no", "off"}:
            continue
        supplier_id = _mot_text(row.get("supplier_id", ""))
        if supplier_id:
            out.append(row)
    return out


def _f_active_email_supplier_rows(base: Path) -> list[dict[str, str]]:
    registry_path = base / "config" / "feeder" / "price_list_manager" / "suppliers.csv"
    rows = read_csv_rows(registry_path)
    out: list[dict[str, str]] = []
    for row in rows:
        active = _mot_text(row.get("active_flag", "")).lower()
        source_type = _mot_text(row.get("source_type", "")).lower()
        source_subtype = _mot_text(row.get("source_subtype", "")).lower()
        if active in {"", "0", "false", "no", "off"}:
            continue
        if source_type == "email_attachment" and source_subtype == "daily_email":
            out.append(row)
    return out


def _f_active_url_supplier_rows(base: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in _f_active_supplier_rows(base):
        source_type = _mot_text(row.get("source_type", "")).lower()
        source_subtype = _mot_text(row.get("source_subtype", "")).lower()
        if source_type in {"api_pull", "url_download"} and source_subtype == "csv_link":
            out.append(row)
    return out


def _source_proof_age_hours(source_row: dict[str, str], batch_row: dict[str, str], now: datetime) -> float | None:
    times: list[datetime] = []
    for field in [
        source_row.get("checked_at_utc", ""),
        source_row.get("latest_source_mtime_utc", ""),
        batch_row.get("updated_at_utc", ""),
        batch_row.get("source_received_at_utc", ""),
    ]:
        parsed = parse_utc(field)
        if parsed is not None:
            times.append(parsed)
    if not times:
        return None
    return max((now - max(times)).total_seconds() / 3600.0, 0.0)


def _batch_import_age_hours(batch_row: dict[str, str], now: datetime) -> float | None:
    times: list[datetime] = []
    for field in [
        batch_row.get("updated_at_utc", ""),
        batch_row.get("source_received_at_utc", ""),
    ]:
        parsed = parse_utc(field)
        if parsed is not None:
            times.append(parsed)
    if not times:
        return None
    return max((now - max(times)).total_seconds() / 3600.0, 0.0)


def _f_source_intake_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    registry_path = base / "config" / "feeder" / "price_list_manager" / "suppliers.csv"
    acquisition_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv"
    batches_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "price_list_batches.csv"
    batch_rows_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "batch_rows.csv"
    active_suppliers = _f_active_supplier_rows(base)
    active_ids = sorted(_mot_text(row.get("supplier_id", "")) for row in active_suppliers if _mot_text(row.get("supplier_id", "")))
    source_rows = read_csv_rows(acquisition_path)
    batch_rows = read_csv_rows(batches_path)
    source_by_supplier = {
        supplier_id: _latest_for_supplier(source_rows, supplier_id, time_field="checked_at_utc")
        for supplier_id in active_ids
    }
    batch_by_supplier = {
        supplier_id: _latest_for_supplier(batch_rows, supplier_id, time_field="updated_at_utc")
        for supplier_id in active_ids
    }
    def import_proven_for(supplier_id: str) -> bool:
        batch = batch_by_supplier.get(supplier_id, {})
        return (
            _mot_text(batch.get("batch_status", "")).lower() in {"imported_from_source", "recovery_resume_ready"}
            and _mot_int(batch.get("source_row_count", "0")) > 0
            and _mot_int(batch.get("valid_row_count", "0")) > 0
            and bool(_existing_path(base, batch.get("source_file_path", "")))
        )

    missing_source_ids = sorted(supplier_id for supplier_id, row in source_by_supplier.items() if not row)
    unclassified_ids = sorted(
        supplier_id
        for supplier_id, row in source_by_supplier.items()
        if row and (not _mot_text(row.get("source_state", "")) or not _mot_text(row.get("status", "")))
    )
    source_failed_ids = sorted(
        supplier_id
        for supplier_id, row in source_by_supplier.items()
        if row
        and (
            _mot_text(row.get("status", "")).lower() == "fail"
            or _mot_text(row.get("source_state", "")).lower() in {"error", "config_needed"}
        )
    )
    failed_with_import_fallback_ids = sorted(supplier_id for supplier_id in source_failed_ids if import_proven_for(supplier_id))
    failed_ids = sorted(set(source_failed_ids) - set(failed_with_import_fallback_ids))
    failed_import_too_old_ids = sorted(
        supplier_id
        for supplier_id in failed_with_import_fallback_ids
        if status_from_age(
            _batch_import_age_hours(batch_by_supplier.get(supplier_id, {}), now),
            warn_hours=F_TEST_MODE_WARN_HOURS,
            fail_hours=F_TEST_MODE_FAIL_HOURS,
        )
        == "fail"
    )
    ready_ids = sorted(
        supplier_id
        for supplier_id, row in source_by_supplier.items()
        if row and _mot_text(row.get("source_state", "")).lower() == "ready"
    )
    ready_imported_ids = sorted(
        supplier_id
        for supplier_id in ready_ids
        if _mot_text(batch_by_supplier.get(supplier_id, {}).get("batch_status", "")).lower()
        in {"imported_from_source", "recovery_resume_ready"}
        and _mot_int(batch_by_supplier.get(supplier_id, {}).get("source_row_count", "0")) > 0
    )
    ready_not_imported_ids = sorted(set(ready_ids) - set(ready_imported_ids))
    waiting_or_missing_count = sum(
        1
        for row in source_by_supplier.values()
        if row and _mot_text(row.get("source_state", "")).lower() in {"missing", "waiting", "download_ready", "green"}
    )
    batch_row_count = csv_row_count(batch_rows_path)
    acquisition_age = file_age_hours(acquisition_path, now)
    batches_age = file_age_hours(batches_path, now)
    age_values = [age for age in [acquisition_age, batches_age] if age is not None]
    age = max(age_values) if age_values else None
    age_status = status_from_age(age, warn_hours=F_TEST_MODE_WARN_HOURS, fail_hours=F_TEST_MODE_FAIL_HOURS)

    if not registry_path.exists() or not active_ids:
        status = "fail"
        value = "registry_missing" if not registry_path.exists() else "no_active_suppliers"
        root_cause = "F supplier registry is missing or has no active suppliers."
        manager_action = "Restore manager-readable F supplier registry proof. Do not run source checks or F061 from MOT."
    elif not acquisition_path.exists() or not source_rows:
        status = "fail"
        value = "source_status_missing"
        root_cause = "FPM010 source acquisition status proof is missing."
        manager_action = "Create a manager-proof task for FPM010. Do not check remote links, fetch files, or run F061 from MOT."
    elif missing_source_ids or unclassified_ids:
        status = "fail"
        value = f"missing={len(missing_source_ids)};unclassified={len(unclassified_ids)}"
        root_cause = "At least one active F supplier is missing or unclassified in source acquisition status."
        manager_action = "Repair source status proof only. Do not run source import, edit queues, or touch the scanner."
    elif failed_ids:
        status = "fail"
        value = f"failed={len(failed_ids)}"
        root_cause = "At least one active F supplier source is reporting failed or config-needed source intake proof."
        manager_action = "Create a bounded F source-intake task for the failed supplier proof."
    elif failed_import_too_old_ids:
        status = "fail"
        value = f"failed_import_too_old={len(failed_import_too_old_ids)}"
        root_cause = "At least one F source check failed and its fallback import proof is too old to trust."
        manager_action = "Create a bounded F source-intake refresh task. Do not fetch files, import rows, or run F061 from MOT."
    elif failed_with_import_fallback_ids:
        status = "warn"
        value = f"source_failed_import_fallback={len(failed_with_import_fallback_ids)}"
        root_cause = "At least one F source check failed, but usable prior import proof is still visible."
        manager_action = "Keep the failed source visible as a warning and refresh it through a manager-approved source task."
    elif ready_not_imported_ids:
        status = "warn"
        value = f"ready_waiting_import={len(ready_not_imported_ids)}"
        root_cause = "At least one ready source does not yet have matching FPM011 import proof."
        manager_action = "Keep ready-but-not-imported source proof visible; do not import or move files from MOT."
    elif age_status != "ok":
        status = age_status
        value = "stale"
        root_cause = "F source intake proof is stale."
        manager_action = "Refresh source intake proof through a manager-approved source task, not through scanner repair."
    elif batch_rows and batch_row_count is None:
        status = "fail"
        value = "batch_rows_unreadable"
        root_cause = "FPM011 batch rows proof is not readable."
        manager_action = "Repair batch-row proof only. Do not rewrite batch rows from MOT."
    else:
        status = "ok"
        value = f"classified={len(active_ids)};ready_imported={len(ready_imported_ids)}"
        root_cause = ""
        manager_action = "No action; F source intake and import proof are readable."

    source_states = ",".join(
        f"{supplier_id}:{_mot_text(row.get('source_state', ''))}:{_mot_text(row.get('status', ''))}"
        for supplier_id, row in source_by_supplier.items()
        if row
    )
    import_states = ",".join(
        f"{supplier_id}:{_mot_text(row.get('batch_status', ''))}:{_mot_text(row.get('source_row_count', ''))}/{_mot_text(row.get('valid_row_count', ''))}"
        for supplier_id, row in batch_by_supplier.items()
        if row
    )

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_source_intake_chain_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM010_check_acquisition_sources.py / FPM011_import_ready_sources.py",
            expected_output="out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv and price_list_batches.csv",
            actual_proof=(
                f"registry_exists={1 if registry_path.exists() else 0};active_suppliers={len(active_ids)};"
                f"source_status_exists={1 if acquisition_path.exists() else 0};source_status_rows={len(source_rows)};"
                f"batches_exists={1 if batches_path.exists() else 0};batch_rows_exists={1 if batch_rows_path.exists() else 0};"
                f"batch_rows={'' if batch_row_count is None else batch_row_count};ready={len(ready_ids)};"
                f"ready_imported={len(ready_imported_ids)};waiting_or_missing={waiting_or_missing_count};"
                f"missing={','.join(missing_source_ids)};failed={','.join(failed_ids)};"
                f"source_failed_import_fallback={','.join(failed_with_import_fallback_ids)};"
                f"failed_import_too_old={','.join(failed_import_too_old_ids)};"
                f"source_states={source_states};import_states={import_states};age_hours={_age_text(age)}"
            ),
            age_hours=_age_text(age),
            row_count=str(len(source_rows)) if source_rows else "",
            source_path=str(acquisition_path),
            summary="F source intake proof shows active supplier sources are classified and ready files have import evidence.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Source intake proof only; metadata/read-status checks only; no remote supplier check, no price-file download, "
                "no ready-source import, no supplier file move/delete, no F061 run, no queue edit, no Sheet write, "
                "no price change, no output deletion, no local DB alignment, and no worker restart."
            ),
        )
    ]


def _f_url_source_download_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    registry_path = base / "config" / "feeder" / "price_list_manager" / "suppliers.csv"
    acquisition_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv"
    batches_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "price_list_batches.csv"
    url_suppliers = _f_active_url_supplier_rows(base)
    expected_ids = sorted(_mot_text(row.get("supplier_id", "")) for row in url_suppliers if _mot_text(row.get("supplier_id", "")))
    source_rows = read_csv_rows(acquisition_path)
    batch_rows = read_csv_rows(batches_path)
    supplier_results: list[tuple[str, str, str, float | None]] = []
    proof_rows: list[dict[str, str]] = []

    if not registry_path.exists():
        status = "fail"
        value = "registry_missing"
        root_cause = "F supplier registry is missing, so URL source suppliers cannot be identified."
        manager_action = "Restore manager-readable F supplier registry proof. Do not call supplier URLs from MOT."
    elif not expected_ids:
        status = "not_checked"
        value = "no_active_url_sources"
        root_cause = ""
        manager_action = "No action unless active URL suppliers are expected in F."
    elif not acquisition_path.exists() or not source_rows:
        status = "fail"
        value = "source_status_missing"
        root_cause = "F URL source acquisition status proof is missing."
        manager_action = "Create a manager-proof task for FPM010/FPM013 evidence. Do not download files from MOT."
    else:
        for supplier_id in expected_ids:
            source_row = _latest_for_supplier(source_rows, supplier_id, time_field="checked_at_utc")
            batch_row = _latest_for_supplier(batch_rows, supplier_id, time_field="updated_at_utc")
            if source_row:
                proof_rows.append(source_row)
            state = _mot_text(source_row.get("source_state", "")).lower()
            source_status = _mot_text(source_row.get("status", "")).lower()
            source_location = _mot_text(source_row.get("source_location", ""))
            latest_name = _mot_text(source_row.get("latest_source_name", ""))
            imported = _mot_text(batch_row.get("batch_status", "")).lower() in {
                "imported_from_source",
                "recommendation_ready",
                "recovery_resume_ready",
            }
            source_rows_count = _mot_int(batch_row.get("source_row_count", "0"))
            valid_rows_count = _mot_int(batch_row.get("valid_row_count", "0"))
            file_exists = bool(
                _existing_path(base, source_row.get("latest_source_path", ""))
                or _existing_path(base, batch_row.get("source_file_path", ""))
            )
            url_visible = source_location.lower().startswith(("http://", "https://"))
            age = _source_proof_age_hours(source_row, batch_row, now)
            age_status = (
                status_from_age(age, warn_hours=F_TEST_MODE_WARN_HOURS, fail_hours=F_TEST_MODE_FAIL_HOURS)
                if age is not None
                else "fail"
            )

            if not source_row:
                supplier_status = "fail"
                reason = "no_url_source_status"
            elif source_status == "fail" or state in {"error", "config_needed"}:
                supplier_status = "fail"
                reason = "url_source_failed_or_config_needed"
            elif not url_visible:
                supplier_status = "fail"
                reason = "url_not_visible"
            elif state == "ready" and not latest_name and not imported:
                supplier_status = "fail"
                reason = "downloaded_file_not_visible"
            elif imported and (source_rows_count <= 0 or valid_rows_count <= 0):
                supplier_status = "fail"
                reason = "prior_import_row_counts_not_proven"
            elif imported and not file_exists:
                supplier_status = "warn"
                reason = "prior_import_file_not_found"
            elif state not in {"download_ready", "ready"} and not imported:
                supplier_status = "fail"
                reason = "url_source_not_download_ready_or_imported"
            elif age_status == "fail":
                supplier_status = "fail"
                reason = "url_source_proof_too_old"
            elif age_status == "warn":
                supplier_status = "warn"
                reason = "url_source_proof_getting_old"
            else:
                supplier_status = "ok"
                reason = "url_source_classified"

            supplier_results.append(
                (
                    supplier_id,
                    supplier_status,
                    (
                        f"state={state};reason={reason};imported={1 if imported else 0};"
                        f"source_rows={source_rows_count};valid_rows={valid_rows_count};age_hours={_age_text(age)}"
                    ),
                    age,
                )
            )

        fail_count = sum(1 for _supplier, supplier_status, _proof, _age in supplier_results if supplier_status == "fail")
        warn_count = sum(1 for _supplier, supplier_status, _proof, _age in supplier_results if supplier_status == "warn")
        ok_count = len(supplier_results) - fail_count - warn_count
        if fail_count:
            status = "fail"
            value = f"fail={fail_count}"
            root_cause = "FPM013 URL source proof is missing, failed, or not classifying an active URL supplier."
            manager_action = "Create a bounded F URL-source proof task. Do not call supplier URLs, download files, or run F061 from MOT."
        elif warn_count:
            status = "warn"
            value = f"warn={warn_count}"
            root_cause = "FPM013 URL source proof is readable but incomplete or getting old."
            manager_action = "Refresh URL source proof through a manager-approved source task, not through MOT."
        else:
            status = "ok"
            value = f"classified={ok_count}"
            root_cause = ""
            manager_action = "No action; active F URL source proof is readable."

    status_ages = [age for _supplier, _supplier_status, _proof, age in supplier_results if age is not None]
    age = max(status_ages) if status_ages else file_age_hours(acquisition_path, now)
    proof_text = "|".join(f"{supplier}:{supplier_status}:{proof}" for supplier, supplier_status, proof, _age in supplier_results)

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_url_source_download_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM013_download_ready_url_sources.py",
            expected_output="Existing URL source status and prior import proof; MOT must not call supplier URLs.",
            actual_proof=(
                f"registry_exists={1 if registry_path.exists() else 0};source_status_exists={1 if acquisition_path.exists() else 0};"
                f"batches_exists={1 if batches_path.exists() else 0};expected={','.join(expected_ids)};"
                f"proof_rows={len(proof_rows)};source_status_rows={len(source_rows)};batch_rows={len(batch_rows)};"
                f"suppliers={proof_text};age_hours={_age_text(age)}"
            ),
            age_hours=_age_text(age),
            row_count=str(len(source_rows)) if source_rows else "",
            source_path=str(acquisition_path),
            summary="F URL source proof shows active URL suppliers are classified without MOT downloading files.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "URL source proof only; metadata/read-status checks only; no remote supplier check, no price-file download, "
                "no supplier file move/delete, no F061 run, no queue edit, no Sheet write, no price change, "
                "no output deletion, no local DB alignment, and no worker restart."
            ),
        )
    ]


def _f_email_price_list_source_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    registry_path = base / "config" / "feeder" / "price_list_manager" / "suppliers.csv"
    acquisition_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv"
    batches_path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "price_list_batches.csv"
    token_path = base / "secrets" / "price_list_manager" / "gmail_token.json"
    client_path = base / "secrets" / "price_list_manager" / "gmail_client_secret.json"
    active_email_suppliers = _f_active_email_supplier_rows(base)
    expected_ids = sorted(_mot_text(row.get("supplier_id", "")) for row in active_email_suppliers if _mot_text(row.get("supplier_id", "")))
    rows = read_csv_rows(acquisition_path)
    batch_rows = read_csv_rows(batches_path)
    token_exists = token_path.exists()
    client_exists = client_path.exists()
    proof_rows: list[dict[str, str]] = []
    supplier_results: list[tuple[str, str, str, float | None]] = []
    luke_needed = False

    if not registry_path.exists():
        status = "fail"
        value = "registry_missing"
        root_cause = "F supplier registry is missing, so active email suppliers cannot be identified."
        manager_action = "Restore manager-readable supplier registry proof. Do not fetch Gmail or run F061 from MOT."
    elif not active_email_suppliers:
        status = "not_checked"
        value = "no_active_email_suppliers"
        root_cause = ""
        manager_action = "No action unless an active email supplier is expected in the F registry."
    else:
        for supplier in active_email_suppliers:
            supplier_id = _mot_text(supplier.get("supplier_id", "")).lower()
            supplier_name = _mot_text(supplier.get("supplier_name", "")) or supplier_id
            expected_label = _expected_f_gmail_label(base, supplier_id, supplier_name)
            source_row = _latest_for_supplier(rows, supplier_id, time_field="checked_at_utc")
            batch_row = _latest_for_supplier(batch_rows, supplier_id, time_field="updated_at_utc")
            if source_row:
                proof_rows.append(source_row)
            notes = _mot_text(source_row.get("notes", ""))
            notes_lower = notes.lower()
            source_location = _mot_text(source_row.get("source_location", ""))
            label_seen = source_location == f"gmail_label:{expected_label}" or f"label={expected_label}".lower() in notes_lower
            downloaded = "gmail_attachment_downloaded" in notes_lower
            no_match = "gmail_no_matching_attachment" in notes_lower
            fetch_error = (
                "gmail_fetch_error" in notes_lower
                or _mot_text(source_row.get("status", "")).lower() == "fail"
                or _mot_text(source_row.get("source_state", "")).lower() == "error"
            )
            source_rows = _mot_int(batch_row.get("source_row_count", "0"))
            valid_rows = _mot_int(batch_row.get("valid_row_count", "0"))
            imported = _mot_text(batch_row.get("batch_status", "")).lower() == "imported_from_source"
            imported_email_attachment = (
                imported and _mot_text(batch_row.get("source_type", "")).lower() == "email_attachment"
            )
            source_file_exists = bool(
                _existing_path(base, batch_row.get("source_file_path", ""))
                or _existing_path(base, source_row.get("latest_source_path", ""))
            )
            age = _source_proof_age_hours(source_row, batch_row, now)
            import_age = _batch_import_age_hours(batch_row, now)
            prior_import_proven = imported and source_rows > 0 and valid_rows > 0 and source_file_exists
            import_label_fallback = imported_email_attachment and prior_import_proven
            label_proven = label_seen or import_label_fallback
            decision_age = import_age if (fetch_error and prior_import_proven) or (import_label_fallback and not label_seen) else age
            age_status = (
                status_from_age(age, warn_hours=F_GMAIL_SOURCE_WARN_HOURS, fail_hours=F_GMAIL_SOURCE_FAIL_HOURS)
                if age is not None
                else "fail"
            )
            decision_age_status = (
                status_from_age(decision_age, warn_hours=F_GMAIL_SOURCE_WARN_HOURS, fail_hours=F_GMAIL_SOURCE_FAIL_HOURS)
                if decision_age is not None
                else "fail"
            )

            if not token_exists or not client_exists:
                supplier_status = "decision_needed"
                reason = "local_gmail_oauth_missing"
                luke_needed = True
            elif not source_row:
                supplier_status = "fail"
                reason = "no_fpm016_proof"
            elif fetch_error and not label_proven:
                supplier_status = "fail"
                reason = "expected_label_not_proven"
            elif fetch_error and not prior_import_proven:
                supplier_status = "fail"
                reason = "gmail_fetch_error"
            elif fetch_error and decision_age_status == "fail":
                supplier_status = "fail"
                reason = "gmail_fetch_error_prior_import_too_old"
            elif fetch_error and decision_age_status == "warn":
                supplier_status = "warn"
                reason = "gmail_fetch_error_prior_import_getting_old"
            elif fetch_error:
                supplier_status = "ok"
                reason = "gmail_fetch_error_prior_import_proven"
            elif not label_proven:
                supplier_status = "fail"
                reason = "expected_label_not_proven"
            elif no_match and imported:
                supplier_status = "warn"
                reason = "latest_attachment_waiting_import_fallback"
            elif no_match and not imported:
                supplier_status = "fail"
                reason = "attachment_not_proven"
            elif not downloaded and not imported:
                supplier_status = "fail"
                reason = "attachment_visibility_not_proven"
            elif not imported or source_rows <= 0 or valid_rows <= 0:
                supplier_status = "fail"
                reason = "import_row_counts_not_proven"
            elif not source_file_exists:
                supplier_status = "fail"
                reason = "imported_source_file_missing"
            elif age_status == "fail":
                supplier_status = "fail"
                reason = "gmail_proof_too_old"
            elif age_status == "warn":
                supplier_status = "warn"
                reason = "gmail_proof_getting_old"
            else:
                supplier_status = "ok"
                reason = (
                    "email_attachment_import_proven_after_local_source_refresh"
                    if import_label_fallback and not label_seen
                    else "label_attachment_and_import_proven"
                )

            supplier_results.append(
                (
                    supplier_id,
                    supplier_status,
                    (
                        f"label={expected_label};reason={reason};source_rows={source_rows};valid_rows={valid_rows};"
                        f"age_hours={_age_text(decision_age)};import_age_hours={_age_text(import_age)}"
                    ),
                    decision_age,
                )
            )

        fail_count = sum(1 for _supplier, supplier_status, _proof, _age in supplier_results if supplier_status == "fail")
        warn_count = sum(1 for _supplier, supplier_status, _proof, _age in supplier_results if supplier_status == "warn")
        decision_count = sum(1 for _supplier, supplier_status, _proof, _age in supplier_results if supplier_status == "decision_needed")
        ok_count = len(supplier_results) - fail_count - warn_count - decision_count
        if decision_count:
            status = "decision_needed"
            value = f"decision={decision_count}"
            root_cause = "The local Gmail OAuth files needed by FPM016 are missing."
            manager_action = "Luke must authorize the local F Gmail source before this manager proof can be trusted."
        elif fail_count:
            status = "fail"
            value = f"fail={fail_count}"
            root_cause = "FPM016 has not left enough outside proof that the active Gmail label and attachment are visible and imported."
            manager_action = "Create a bounded FPM016 manager-proof task. Do not download attachments, delete Gmail, run F061, or edit queues."
        elif warn_count:
            status = "warn"
            value = f"warn={warn_count}"
            root_cause = "FPM016 proof exists, but it is getting old."
            manager_action = "Refresh this as a manager proof task before relying on it for new supplier coverage."
        else:
            status = "ok"
            value = f"ready={ok_count}"
            root_cause = ""
            manager_action = "No action; active F Gmail price-list source proof is current enough for manager control."

    status_ages = [age for _supplier, _supplier_status, _proof, age in supplier_results if age is not None]
    age = max(status_ages) if status_ages else file_age_hours(acquisition_path, now)
    proof_text = "|".join(f"{supplier}:{supplier_status}:{proof}" for supplier, supplier_status, proof, _age in supplier_results)

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_email_price_list_source_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM016_fetch_gmail_email_sources.py",
            expected_output="FPM016 local Gmail proof plus FPM011 import row counts, read only by MOT.",
            actual_proof=(
                f"registry_exists={1 if registry_path.exists() else 0};source_status_exists={1 if acquisition_path.exists() else 0};"
                f"batches_exists={1 if batches_path.exists() else 0};token_exists={1 if token_exists else 0};"
                f"client_secret_exists={1 if client_exists else 0};expected={','.join(expected_ids)};"
                f"proof_rows={len(proof_rows)};source_status_rows={len(rows)};batch_rows={len(batch_rows)};"
                f"suppliers={proof_text};age_hours={_age_text(age)}"
            ),
            age_hours=_age_text(age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(acquisition_path),
            summary="F email price-list source proof shows active Gmail attachment suppliers without MOT fetching mail.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if luke_needed else "0",
            safe_repair_boundary=(
                "Email price-list proof only; metadata/read-status checks only; no Gmail fetch, no attachment download, "
                "no Gmail deletion, no local file deletion, no F061 run, no queue edit, no Sheet write, no price change, "
                "no output deletion, no local DB alignment, and no worker restart."
            ),
        )
    ]


def _f_login_mode_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    browser_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_browser_visibility_state.txt"
    request_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_login_mode.requested"
    browser = _read_lock_fields(browser_path)
    request = _read_lock_fields(request_path)
    request_status = str(request.get("status", "")).strip().lower()
    auth_state = str(browser.get("auth_state", "")).strip().lower()
    request_age = _field_age_seconds(request, now, "last_observed_utc", "requested_utc")

    if not request_path.exists():
        status = "ok"
        value = "not_requested"
        root_cause = ""
        manager_action = "No action; login mode is not requested."
    elif request_status == "drained" or auth_state == "logged_in":
        status = "ok"
        value = request_status or auth_state
        root_cause = ""
        manager_action = "No action; login evidence is drained or authenticated."
    elif request_status in {"requested", "active", "pending", "login_recovery"}:
        status = "decision_needed"
        value = request_status
        root_cause = "F login recovery is waiting for script-owned browser action."
        manager_action = "Use only the normal F061 script-owned browser path if Luke approves login recovery."
    elif request_age is not None and request_age >= F_CHILD_FAIL_SECONDS:
        status = "fail"
        value = request_status or "stale"
        root_cause = "F login mode request is stale and not drained."
        manager_action = "Classify login recovery state before running any scanner proof."
    else:
        status = "warn"
        value = request_status or "unclassified"
        root_cause = "F login mode state is not classified."
        manager_action = "Classify login state without opening a separate maintenance browser."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_login_mode_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM130_run_live_cycle.py",
            expected_output="out/systems/F/price_list_manager/live/f061_login_mode.requested",
            actual_proof=(
                f"request_exists={1 if request_path.exists() else 0};request_status={request_status};"
                f"auth_state={auth_state};request_age_seconds={_seconds_text(request_age)}"
            ),
            source_path=str(request_path),
            summary="F login mode is either clear or waiting on a script-owned browser decision.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if status == "decision_needed" else "0",
            safe_repair_boundary="Login proof only; no separate Chrome workaround, no scanner run, no worker restart.",
        )
    ]


def _row_age_hours(row: dict[str, str], now: datetime, *, field: str = "observed_utc") -> float | None:
    parsed = parse_utc(str(row.get(field, "")))
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600.0)


def _f_bbp_account_login_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    proof_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "bbp_login_recovery_proof.csv"
    browser_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_browser_visibility_state.txt"
    rows = read_csv_rows(proof_path)
    latest = _latest_csv_row(rows)
    browser = _read_lock_fields(browser_path)
    proof_status = str(latest.get("status", "")).strip().lower()
    proof_reason = str(latest.get("reason", "")).strip().lower()
    auth_state = str(browser.get("auth_state", "")).strip().lower()
    age = _row_age_hours(latest, now) if latest else file_age_hours(proof_path, now)

    if proof_status == "succeeded" or auth_state == "logged_in":
        status = "ok"
        value = "bbp_account_logged_in"
        root_cause = ""
        manager_action = "No action; BBP account login proof is visible."
    elif not proof_path.exists():
        status = "warn"
        value = "missing_proof"
        root_cause = "BBP account login proof is missing."
        manager_action = "Keep BBP login separate from Seller Central eligibility proof."
    else:
        status = "warn"
        value = proof_status or "unclassified"
        root_cause = "Latest BBP account login proof is not a success row."
        manager_action = "Use only the normal F061 scanner-owned browser path for BBP login recovery."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_bbp_account_login_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="Webscrape.py",
            expected_output="out/systems/F/price_list_manager/live/bbp_login_recovery_proof.csv",
            actual_proof=(
                f"proof_exists={1 if proof_path.exists() else 0};proof_rows={len(rows)};"
                f"latest_status={proof_status};latest_reason={proof_reason};auth_state={auth_state};"
                f"age_hours={_age_text(age)}"
            ),
            age_hours=_age_text(age),
            source_path=str(proof_path),
            summary="F BBP account login proof is split from Seller Central eligibility login proof.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="0",
            safe_repair_boundary="BBP account login proof only; no F061 run, no queue edit, no separate Chrome login, no Sheets, no prices.",
        )
    ]


def _f_seller_central_eligibility_auth_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    proof_path = (
        base
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "seller_central_login_recovery_proof.csv"
    )
    secret_path = base / "secrets" / "price_list_manager" / "seller_central_login.env"
    rows = read_csv_rows(proof_path)
    latest = _latest_csv_row(rows)
    proof_status = str(latest.get("status", "")).strip().lower()
    proof_reason = str(latest.get("reason", "")).strip().lower()
    code_seen = str(latest.get("code_seen_flag", "")).strip()
    fresh_code = str(latest.get("fresh_code_flag", "")).strip()
    used_message = str(latest.get("used_message_flag", "")).strip()
    succeeded = str(latest.get("succeeded_flag", "")).strip()
    enabled = str(latest.get("auto_login_enabled", "")).strip()
    credentials_present = str(latest.get("credentials_present", "")).strip()
    age = _row_age_hours(latest, now) if latest else file_age_hours(proof_path, now)
    f_owned_login_reasons = {
        "email_continue_not_advanced",
        "otp_page_not_detected",
        "password_not_entered",
        "signin_or_passkey_page_after_code_wait",
        "signin_or_passkey_page_after_credentials",
        "sms_option_not_clickable",
        "signin_selectors_missing",
        "submit_not_accepted",
        "otp_selectors_missing",
        "eligibility_signal_not_visible_after_code",
        "bbp_dashboard_not_refreshed_after_seller_central",
    }
    luke_login_reasons = {
        "amazon_forced_passkey",
        "manual_challenge_required",
        "authenticator_only_no_sms_option",
        "missing_secret_file",
        "missing_credentials",
        "auto_login_disabled",
        "password_rejected",
    }

    if not proof_path.exists():
        status = "warn"
        value = "missing_proof"
        root_cause = "Seller Central eligibility login has no proof yet."
        manager_action = "Create a controlled Seller Central eligibility proof packet before calling F fully eligibility-ready."
        luke_needed = False
    elif proof_status == "succeeded" and succeeded == "1" and (age is None or age < F_REVIEW_WARN_HOURS):
        status = "ok"
        value = "eligibility_auth_proved"
        root_cause = ""
        manager_action = "No action; Seller Central eligibility proof is current."
        luke_needed = False
    elif proof_status == "succeeded":
        status = "warn"
        value = "stale_success"
        root_cause = "Seller Central eligibility proof succeeded before, but it is stale."
        manager_action = "Refresh only through an approved F proof window."
        luke_needed = False
    elif proof_status == "waiting_for_code":
        status = "warn"
        value = proof_reason or proof_status
        root_cause = "F is waiting for the approved Seller Central code source, not a Luke business decision."
        manager_action = "Keep F-BROWSER-SESSION-DURABILITY active and classify the next page proof. Ask Luke only if Amazon shows a real manual challenge."
        luke_needed = False
    elif proof_status == "blocked" and proof_reason in f_owned_login_reasons:
        status = "warn"
        value = proof_reason or proof_status
        root_cause = "F has a scanner-owned login page classification problem, not a user decision."
        manager_action = "Continue F-BROWSER-SESSION-DURABILITY and retest through the next natural scanner-owned login challenge."
        luke_needed = False
    elif proof_status in {"disabled", "blocked"} and proof_reason in luke_login_reasons:
        status = "decision_needed"
        value = proof_reason or proof_status
        root_cause = "Seller Central eligibility login needs a real protected login input that F cannot safely complete by itself."
        manager_action = "Ask Luke only for the exact manual challenge or missing credential/source decision."
        luke_needed = True
    elif proof_status in {"disabled", "blocked"}:
        status = "warn"
        value = proof_reason or proof_status
        root_cause = "Seller Central eligibility login is blocked, but the latest proof does not yet show a protected Luke decision."
        manager_action = "Classify the blocked page inside the F login/session durability packet before asking Luke."
        luke_needed = False
    elif proof_status in {"failed", "expired"}:
        status = "fail"
        value = proof_reason or proof_status
        root_cause = "Seller Central eligibility login proof failed or timed out."
        manager_action = "Create a bounded worker repair packet; do not edit queues or rerun F061 outside approval."
        luke_needed = False
    elif proof_status == "otp_intake_proved" and code_seen == "1" and fresh_code == "1":
        status = "warn"
        value = "otp_intake_visible_not_live_proved"
        root_cause = "Seller Central OTP Gmail intake can see a fresh code, but F061 has not live-proved eligibility login yet."
        manager_action = "Use this as read-only OTP proof only; live Seller Central proof still needs an approved F061 proof window."
        luke_needed = False
    elif proof_status == "otp_intake_missing":
        status = "warn"
        value = proof_reason or "otp_intake_missing"
        root_cause = "Seller Central OTP Gmail intake did not see a fresh unused code in the proof window."
        manager_action = "Send one fresh AmazonOTP-labelled test email, then rerun the read-only OTP proof. Do not run F061 for this check."
        luke_needed = False
    else:
        status = "warn"
        value = proof_status or "unclassified"
        root_cause = "Seller Central eligibility login proof is present but unclassified."
        manager_action = "Classify the proof without running F061."
        luke_needed = False

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_seller_central_eligibility_auth_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="seller_central_login_recovery.py",
            expected_output="out/systems/F/price_list_manager/live/seller_central_login_recovery_proof.csv",
            actual_proof=(
                f"proof_exists={1 if proof_path.exists() else 0};proof_rows={len(rows)};"
                f"secret_exists={1 if secret_path.exists() else 0};latest_status={proof_status};"
                f"latest_reason={proof_reason};enabled={enabled};credentials_present={credentials_present};"
                f"code_seen={code_seen};fresh_code={fresh_code};used_message={used_message};"
                f"succeeded={succeeded};age_hours={_age_text(age)}"
            ),
            age_hours=_age_text(age),
            source_path=str(proof_path),
            summary="F Seller Central eligibility login proof is checked separately from BBP account login.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if luke_needed else "0",
            safe_repair_boundary=(
                "Seller Central eligibility proof only; no F061 run without approved proof window, no separate Chrome login, "
                "no queue edit, no price change, no Sheets, no local DB alignment, no output deletion, and no worker restart."
            ),
        )
    ]


def _f_visible_login_control_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    request_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_visible_login.requested"
    browser_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_browser_visibility_state.txt"
    launch_path = base / "out" / "systems" / "F" / "diagnostics" / "fpm160_visible_login_launch_status.json"
    global_path = base / "out" / "locks" / "maintenance.requested"
    request = _read_lock_fields(request_path)
    browser = _read_lock_fields(browser_path)
    launch = _read_json(launch_path)
    request_status = str(request.get("status", "")).strip().lower()
    auth_state = str(browser.get("auth_state", "")).strip().lower()
    launch_status = str(launch.get("status", "")).strip().lower()
    launch_age = file_age_hours(launch_path, now)
    request_age = _field_age_seconds(request, now, "requested_utc", "updated_utc", "last_observed_utc")
    global_request_text = ""
    if global_path.exists():
        try:
            global_request_text = global_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            global_request_text = ""
    f_global_request = "FPM160_f061_visible_login_maintenance" in global_request_text

    if request_path.exists():
        status = "decision_needed"
        value = request_status or "requested"
        root_cause = "A separate visible-login maintenance request is active for F."
        manager_action = "Do not open a separate browser from MOT. Keep F login recovery on the normal script-owned F061 path unless Luke approves otherwise."
    elif f_global_request:
        status = "decision_needed"
        value = "global_request"
        root_cause = "A legacy global maintenance request appears to have been created by FPM160."
        manager_action = "Classify and clear the F-only maintenance request only through an approved manager task."
    elif launch_status in {"failed", "blocked"} and launch_age is not None and launch_age <= F_REVIEW_WARN_HOURS:
        status = "warn"
        value = launch_status
        root_cause = "Recent FPM160 launch evidence reports a blocked or failed separate-login attempt."
        manager_action = "Keep this as evidence only; do not retry browser launch from MOT."
    else:
        status = "ok"
        value = "clear"
        root_cause = ""
        manager_action = "No action; no active separate visible-login maintenance request is visible."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_visible_login_control_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM160_f061_visible_login_maintenance.py",
            expected_output="out/systems/F/price_list_manager/live/f061_visible_login.requested",
            actual_proof=(
                f"request_exists={1 if request_path.exists() else 0};request_status={request_status};"
                f"request_age_seconds={_seconds_text(request_age)};auth_state={auth_state};"
                f"launch_status={launch_status};launch_age_hours={_age_text(launch_age)};"
                f"f_global_request={1 if f_global_request else 0}"
            ),
            age_hours=_age_text(launch_age),
            source_path=str(request_path),
            summary="F visible-login maintenance state is manager-visible without opening a separate browser.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if status == "decision_needed" else "0",
            safe_repair_boundary=(
                "Visible-login proof only; no separate Chrome login window, no F061 run, no worker restart, "
                "no maintenance-marker change, and no queue edit."
            ),
        )
    ]


def _f_queue_handoff_control_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    test_dir = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    controls_path = test_dir / "queue_controls.csv"
    approvals_path = test_dir / "f061_handoff_approvals.csv"
    decisions_path = test_dir / "manager_decisions.csv"
    controls = read_csv_rows(controls_path)
    approvals = read_csv_rows(approvals_path)
    decisions = read_csv_rows(decisions_path)
    approved = [row for row in approvals if str(row.get("approval_state", "")).strip().lower() == "approved"]
    active_controls = [
        row
        for row in controls
        if str(row.get("control_state", "")).strip().lower() not in {"", "cleared", "inactive", "disabled"}
    ]
    safe_decisions = [
        row
        for row in decisions
        if str(row.get("safe_to_handoff_flag", "")).strip() in {"1", "true", "True", "yes", "YES"}
    ]
    unclassified_approvals = [
        row
        for row in approvals
        if str(row.get("approval_state", "")).strip().lower()
        not in {"approved", "rejected", "expired", "blocked", "pending", "cancelled", "canceled"}
    ]

    if not controls_path.exists() and not approvals_path.exists() and not decisions_path.exists():
        status = "warn"
        value = "missing"
        root_cause = "F queue and handoff control proof files are missing."
        manager_action = "Restore manager-visible control proof before making handoff decisions."
    elif unclassified_approvals:
        status = "warn"
        value = f"unclassified_approvals={len(unclassified_approvals)}"
        root_cause = "At least one handoff approval row has an unclassified state."
        manager_action = "Classify the approval state before trusting handoff proof."
    elif safe_decisions and not approved:
        status = "decision_needed"
        value = "handoff_waiting"
        root_cause = "A manager decision says handoff is safe, but no approval proof is visible."
        manager_action = "Do not approve handoff from MOT. Create a protected approval task if handoff is required."
    else:
        status = "ok"
        value = f"controls={len(active_controls)};approvals={len(approved)}"
        root_cause = ""
        manager_action = "No action; queue control and handoff approval evidence are readable."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_queue_handoff_control_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM040/FPM080/FPM090 queue and handoff control",
            expected_output="out/systems/F/price_list_manager/test_mode/queue_controls.csv and f061_handoff_approvals.csv",
            actual_proof=(
                f"controls_exists={1 if controls_path.exists() else 0};control_rows={len(controls)};"
                f"active_controls={len(active_controls)};approvals_exists={1 if approvals_path.exists() else 0};"
                f"approval_rows={len(approvals)};approved_rows={len(approved)};"
                f"decisions_exists={1 if decisions_path.exists() else 0};safe_decisions={len(safe_decisions)}"
            ),
            row_count=str(len(controls) + len(approvals) + len(decisions)),
            source_path=str(controls_path),
            summary="F queue controls and F061 handoff approvals are visible without changing the queue.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if status == "decision_needed" else "0",
            safe_repair_boundary="Queue/handoff proof only; no queue edit, no handoff approval, no F061 run, no Sheet write, and no price change.",
        )
    ]


def _f_rescan_priority_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    policy_path = base / "config" / "feeder" / "f_scanner_timeout_policy.csv"
    active_path = base / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    screening_path = base / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv"
    preview_summary_path = (
        base
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "test_mode"
        / "f061_rescan_recovery_summary.csv"
    )
    policy_rows = read_csv_rows(policy_path)
    active_rows = read_csv_rows(active_path)
    screening_rows = read_csv_rows(screening_path)
    preview_summary_rows = read_csv_rows(preview_summary_path)
    latest_preview = _latest_csv_row(preview_summary_rows, time_field="built_at_utc")
    preview_total = _mot_int(latest_preview.get("total_parked_rows", "0"))
    preview_requeue = _mot_int(latest_preview.get("requeue_rows", "0"))
    preview_exhausted = _mot_int(latest_preview.get("retry_exhausted_rows", "0"))
    preview_source_blocked = _mot_int(latest_preview.get("source_blocked_rows", "0"))
    rescan_policy = next(
        (row for row in policy_rows if _mot_text(row.get("fail_code", "")).upper() == "RESCAN"),
        {},
    )
    rescan_mode = _mot_text(rescan_policy.get("timeout_mode", "")).lower()
    rescan_enabled = _mot_text(rescan_policy.get("enabled", ""))
    timeout_days = _mot_text(rescan_policy.get("timeout_days", ""))
    max_timeout_days = _mot_text(rescan_policy.get("max_timeout_days", ""))
    rescan_policy_has_cooldown = bool(
        rescan_policy
        and rescan_mode != "disabled"
        and rescan_enabled != "0"
        and (timeout_days not in {"", "0"} or max_timeout_days not in {"", "0"})
    )
    active_rescan_pending = [
        row
        for row in active_rows
        if _mot_text(row.get("scan_status", "")).lower() == "pending"
        and _mot_text(row.get("scan_reason", "")).lower() == "rescan_retry_required"
        and _mot_text(row.get("completion_block_reason", "")).lower() == "rescan_retry_pending"
    ]
    retry_visible = [
        row
        for row in screening_rows
        if _mot_text(row.get("row_status", "")).lower() == "retry"
        and _mot_text(row.get("fail_code", "")).upper() == "RESCAN"
        and not _mot_text(row.get("timeout_until_utc", ""))
    ]
    exhausted_visible = [
        row
        for row in screening_rows
        if _mot_text(row.get("fail_code", "")).upper() == "RESCAN"
        and "retry_exhausted" in _mot_text(row.get("status_reason", "")).lower()
        and not _mot_text(row.get("timeout_until_utc", ""))
    ]
    rescan_timeout_rows = [
        row
        for row in screening_rows
        if (
            _mot_text(row.get("fail_code", "")).upper() == "RESCAN"
            or _mot_text(row.get("pf", "")).upper() == "RESCAN"
        )
        and bool(_mot_text(row.get("timeout_until_utc", "")))
    ]

    if not policy_path.exists() or not rescan_policy:
        status = "fail"
        value = "policy_missing"
        root_cause = "F RESCAN timeout policy is missing, so the manager cannot prove retry-now behavior."
        manager_action = "Restore the RESCAN policy row as disabled cooldown before trusting F RESCAN behavior."
    elif rescan_policy_has_cooldown:
        status = "fail"
        value = "rescan_cooldown_enabled"
        root_cause = "RESCAN still has a timeout/cooldown policy, which parks retry rows instead of rescanning them."
        manager_action = "Remove RESCAN cooldown from the policy. Do not edit the live F061 queue from MOT."
    elif rescan_timeout_rows:
        status = "fail"
        value = f"parked_timeout={len(rescan_timeout_rows)}"
        root_cause = "Existing RESCAN rows still carry timeout dates, so they are parked instead of retry-now."
        preview_text = (
            f" Preview exists: requeue={preview_requeue};exhausted={preview_exhausted};"
            f"source_blocked={preview_source_blocked}."
            if preview_total == len(rescan_timeout_rows)
            else ""
        )
        manager_action = (
            "Needs protected decision: approve a preview-first F rescan recovery packet for the parked rows, "
            "or leave them parked. Do not rewrite queue/output rows from MOT."
            + preview_text
        )
    elif not active_path.exists() and not screening_path.exists():
        status = "warn"
        value = "proof_missing"
        root_cause = "F RESCAN priority proof files are missing."
        manager_action = "Restore active-run and screening-state proof at a safe F manager boundary."
    else:
        status = "ok"
        value = f"active_retry={len(active_rescan_pending)};retry_visible={len(retry_visible)}"
        root_cause = ""
        manager_action = "No action; RESCAN is configured as same-cycle retry with no cooldown."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_rescan_priority_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="F061 RESCAN retry handling and F timeout policy",
            expected_output="config/feeder/f_scanner_timeout_policy.csv and out/systems/F/live/f_screening_row_state_live.csv",
            actual_proof=(
                f"policy_exists={1 if policy_path.exists() else 0};policy_mode={rescan_mode or '-'};"
                f"policy_enabled={rescan_enabled or '-'};timeout_days={timeout_days or '-'};"
                f"max_timeout_days={max_timeout_days or '-'};active_retry={len(active_rescan_pending)};"
                f"retry_visible={len(retry_visible)};exhausted_visible={len(exhausted_visible)};"
                f"rescan_timeout_rows={len(rescan_timeout_rows)};preview_exists={1 if preview_summary_path.exists() else 0};"
                f"preview_total={preview_total};preview_requeue={preview_requeue};"
                f"preview_exhausted={preview_exhausted};preview_source_blocked={preview_source_blocked}"
            ),
            row_count=str(len(active_rows) + len(screening_rows)),
            source_path=f"{policy_path};{active_path};{screening_path};{preview_summary_path}",
            summary="F RESCAN must mean retry-now for temporary scanner/login/internet issues, not a 30-day timeout.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if rescan_timeout_rows else "0",
            safe_repair_boundary="RESCAN proof only; no F061 run, no worker restart, no queue edit, no output rewrite, no Sheet write, and no price change.",
        )
    ]


def _latest_backtrack_by_key(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            str(row.get("supplier_id", "")).strip(),
            str(row.get("supplier_sku", "")).strip(),
            str(row.get("asin", "")).strip(),
        )
        if not any(key):
            continue
        current = grouped.get(key)
        current_attempt = int(float(current.get("backtrack_attempt_number", "0") or 0)) if current else -1
        try:
            attempt = int(float(row.get("backtrack_attempt_number", "0") or 0))
        except ValueError:
            attempt = 0
        current_time = parse_utc(current.get("backtrack_observed_utc", "")) if current else None
        row_time = parse_utc(row.get("backtrack_observed_utc", ""))
        if current is None or attempt > current_attempt or (attempt == current_attempt and row_time and (current_time is None or row_time > current_time)):
            grouped[key] = row
    return list(grouped.values())


def _f_parked_decision_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "F" / "live" / "f_login_backtrack_evidence_live.csv"
    rows = read_csv_rows(path)
    latest_rows = _latest_backtrack_by_key(rows)
    unresolved_statuses = {"dashboard_yes_no_unresolved", "missing_dashboard_yes_no", "login_backtrack_pending"}
    unresolved = [
        row
        for row in latest_rows
        if str(row.get("merged_into_candidate_flag", "")).strip() != "1"
        and (
            str(row.get("backtrack_status", "")).strip().lower() in unresolved_statuses
            or str(row.get("original_status_reason", "")).strip().lower() in unresolved_statuses
        )
    ]
    age_status, age = _file_status_for_age(path, now, warn_hours=F_REVIEW_WARN_HOURS, fail_hours=F_REVIEW_FAIL_HOURS)

    if not path.exists():
        status = "warn"
        value = "missing"
        root_cause = "F login backtrack decision proof is missing."
        manager_action = "Restore decision proof before publishing any recovered F rows."
    elif unresolved:
        sample = unresolved[0]
        value = str(len(unresolved))
        root_cause = (
            f"Unresolved F backtrack row remains parked: supplier_sku={sample.get('supplier_sku', '')};"
            f"asin={sample.get('asin', '')};status={sample.get('backtrack_status', '')}."
        )
        if quiet_autonomy_active(base):
            status = "not_checked"
            value = f"parked_quiet_autonomy:{len(unresolved)}"
            manager_action = (
                "Park the unresolved F backtrack decision during Quiet Autonomy. Do not approve, publish, "
                "queue-edit, or accept the row while Luke is away."
            )
        else:
            status = "decision_needed"
            manager_action = "Keep the row parked until Luke approves an exception or a targeted authenticated recovery proves it."
    elif age_status == "fail":
        status = "fail"
        value = "stale"
        root_cause = "F decision proof is too stale to trust."
        manager_action = "Refresh decision proof before moving F review rows."
    elif age_status == "warn":
        status = "warn"
        value = "stale"
        root_cause = "F decision proof is readable but stale."
        manager_action = "Refresh decision proof at a safe manager boundary."
    else:
        status = "ok"
        value = "0"
        root_cause = ""
        manager_action = "No action; no parked login-backtrack decision rows are visible."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_parked_decision_rows",
            status=status,
            severity=_severity(status),
            value=value,
            producer="F061 login backtrack merge proof",
            expected_output="out/systems/F/live/f_login_backtrack_evidence_live.csv",
            actual_proof=f"exists={1 if path.exists() else 0};latest_rows={len(latest_rows)};unresolved={len(unresolved)};age_hours={_age_text(age)}",
            age_hours=_age_text(age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(path),
            summary="Parked F decision rows remain blocked until recovered or explicitly approved.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required="1" if status == "decision_needed" else "0",
            safe_repair_boundary="Decision proof only; do not publish, approve, queue-edit, or accept parked Entertainment Trading rows.",
        )
    ]


def _f_recovery_progress_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "f061_recovery_progress.csv"
    rows = read_csv_rows(path)
    latest = _latest_csv_row(rows, time_field="imported_at_utc")
    pending_unmatched = _mot_int(latest.get("pending_unmatched_rows", "0"))
    pending_source = _mot_int(latest.get("pending_source_rows", "0"))
    pending_matched = _mot_int(latest.get("pending_matched_rows", "0"))
    pending_held = _mot_int(latest.get("pending_held_rows", "0"))

    if not path.exists() or not rows:
        status = "warn"
        value = "missing"
        root_cause = "F recovery progress proof is missing or empty."
        manager_action = "Keep recovery progress unproven until existing proof is restored. Do not import recovery data from MOT."
    elif pending_unmatched:
        status = "fail"
        value = f"unmatched={pending_unmatched}"
        root_cause = "F recovery progress has pending rows that were not matched or held."
        manager_action = "Create a bounded F recovery-proof task. Do not merge rows or edit queues from MOT."
    else:
        status = "ok"
        value = "reconciled"
        root_cause = ""
        manager_action = "No action; recovery progress proof is reconciled."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_recovery_progress_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM125_import_f061_recovery_progress.py",
            expected_output="out/systems/F/price_list_manager/test_mode/f061_recovery_progress.csv",
            actual_proof=(
                f"exists={1 if path.exists() else 0};rows={len(rows)};supplier={latest.get('supplier_id', '')};"
                f"pending_source={pending_source};pending_matched={pending_matched};"
                f"pending_held={pending_held};pending_unmatched={pending_unmatched}"
            ),
            row_count=str(len(rows)) if rows else "",
            source_path=str(path),
            summary="F recovery progress reconciliation is visible without importing or merging recovery rows.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Recovery proof only; no recovery import, no merge, no F061 queue edit, no F061 run, and no output deletion.",
        )
    ]


def _f_review_handoff_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    manifest_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv"
    quality_path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_gate_quality_report.csv"
    rows = read_csv_rows(manifest_path)
    latest = _latest_csv_row(rows, time_field="built_at_utc")
    age_status, age = _file_status_for_age(manifest_path, now, warn_hours=F_REVIEW_WARN_HOURS, fail_hours=F_REVIEW_FAIL_HOURS)
    quality_rows = read_csv_rows(quality_path)
    operator_ready = str(latest.get("operator_ready_flag", "")).strip()
    ai_gate_status = str(latest.get("ai_gate_status", "")).strip().lower()
    fail_rows = str(latest.get("ai_gate_fail_rows", "0")).strip() or "0"

    if not manifest_path.exists() or not rows:
        status = "warn"
        value = "missing"
        root_cause = "Review handoff manifest is missing or empty."
        manager_action = "Keep review handoff proof untrusted until the manifest exists."
    elif operator_ready == "1" and (ai_gate_status not in {"passed", "ok", "pass"} or fail_rows not in {"0", "0.0"}):
        status = "fail"
        value = ai_gate_status or "blocked"
        root_cause = "Review handoff claims operator-ready rows without clean AI gate proof."
        manager_action = "Block review handoff until AI-gated proof is clean."
    elif age_status == "fail":
        status = "fail"
        value = "stale"
        root_cause = "Review handoff proof is too stale to trust."
        manager_action = "Refresh review handoff proof before promoting rows."
    elif age_status == "warn" or not quality_rows:
        status = "warn"
        value = "stale" if age_status == "warn" else "missing_quality"
        root_cause = "Review handoff or AI quality proof needs refresh."
        manager_action = "Refresh review proof at a safe manager boundary."
    else:
        status = "ok"
        value = ai_gate_status or "ok"
        root_cause = ""
        manager_action = "No action; review handoff is AI-gated."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_review_handoff_ai_gate",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM150/FPM155 review handoff gate",
            expected_output="out/systems/F/price_list_manager/live/review_handoff_manifest.csv",
            actual_proof=(
                f"manifest_exists={1 if manifest_path.exists() else 0};manifest_rows={len(rows)};"
                f"quality_exists={1 if quality_path.exists() else 0};quality_rows={len(quality_rows)};"
                f"operator_ready={operator_ready};ai_gate_status={ai_gate_status};fail_rows={fail_rows};age_hours={_age_text(age)}"
            ),
            age_hours=_age_text(age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(manifest_path),
            summary="Review handoff rows are backed by AI-gated proof before operator review.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Review proof only; no publish, no Sheet write, no scanner run, no queue edit.",
        )
    ]


def _latest_file(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.rglob(pattern) if path.is_file()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime)[-1]


def _status_counts(rows: list[dict[str, str]]) -> tuple[int, int]:
    fail_rows = 0
    warn_rows = 0
    for row in rows:
        status = str(row.get("status", "")).strip().lower()
        if status == "fail":
            fail_rows += 1
        elif status == "warn":
            warn_rows += 1
    return fail_rows, warn_rows


def _f_review_ai_production_readiness_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    live_dir = base / "out" / "systems" / "F" / "price_list_manager" / "live"
    precheck_root = base / "out" / "systems" / "F" / "price_list_manager" / "ai_prechecks"
    review_pack_path = live_dir / "review_pack_build_health.csv"
    quality_path = live_dir / "ai_gate_quality_report.csv"
    production_path = live_dir / "production_line_health.csv"
    rollout_path = live_dir / "split_rollout_readiness.csv"
    precheck_path = _latest_file(precheck_root, "ai_precheck_health.csv")

    review_pack_rows = read_csv_rows(review_pack_path)
    quality_rows = read_csv_rows(quality_path)
    production_rows = read_csv_rows(production_path)
    rollout_rows = read_csv_rows(rollout_path)
    precheck_rows = read_csv_rows(precheck_path) if precheck_path else []
    rollout_summary = next((row for row in rollout_rows if row.get("check") == "f_split_rollout_readiness"), _latest_csv_row(rollout_rows))
    precheck_latest = _latest_csv_row(precheck_rows)
    fail_rows = 0
    warn_rows = 0
    missing: list[str] = []
    for label, path, rows in [
        ("review_pack", review_pack_path, review_pack_rows),
        ("ai_quality", quality_path, quality_rows),
        ("production", production_path, production_rows),
        ("split_rollout", rollout_path, rollout_rows),
    ]:
        if not path.exists() or not rows:
            missing.append(label)
        status_rows = rows
        if label == "production":
            status_rows = [
                row
                for row in rows
                if not str(row.get("check", "")).strip().lower().startswith("f_split_rollout_")
            ]
        elif label == "split_rollout":
            status_rows = [rollout_summary] if rollout_summary else []
        file_fail, file_warn = _status_counts(status_rows)
        fail_rows += file_fail
        warn_rows += file_warn
    if precheck_path:
        file_fail, file_warn = _status_counts(precheck_rows)
        fail_rows += file_fail
        warn_rows += file_warn

    rollout_status = str(rollout_summary.get("status", "")).strip().lower()
    rollout_value = str(rollout_summary.get("value", "")).strip()
    precheck_value = str(precheck_latest.get("value", "") or precheck_latest.get("status", "")).strip()
    age_candidates = [file_age_hours(path, now) for path in [review_pack_path, quality_path, production_path, rollout_path] if path.exists()]
    latest_age = max((age for age in age_candidates if age is not None), default=None)

    if missing:
        status = "warn"
        value = f"missing={','.join(missing)}"
        root_cause = "Some F review, AI, production, or rollout readiness proof is missing."
        manager_action = "Keep missing proof visible and create a bounded manager task only if it blocks an F decision."
    elif rollout_status == "fail" or fail_rows:
        status = "fail"
        value = f"fail_rows={fail_rows}"
        root_cause = "F review, AI, production, or rollout readiness proof contains a failure."
        manager_action = "Create a bounded F proof task. Do not run scanner stages or enable rollout from MOT."
    else:
        status = "ok"
        value = rollout_value or precheck_value or "ready"
        root_cause = ""
        manager_action = "No action; F review, AI, production, and rollout readiness proof is manager-visible."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_review_ai_production_readiness",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM150/FPM155/FPM156/FPM157/FPM180/FPM190 readiness proof",
            expected_output="F review, AI, production-line, and split-rollout proof files",
            actual_proof=(
                f"review_pack_rows={len(review_pack_rows)};ai_quality_rows={len(quality_rows)};"
                f"production_rows={len(production_rows)};split_rollout_rows={len(rollout_rows)};"
                f"precheck_rows={len(precheck_rows)};fail_rows={fail_rows};warn_rows={warn_rows};"
                f"rollout_status={rollout_status};rollout_value={rollout_value};precheck_value={precheck_value}"
            ),
            age_hours=_age_text(latest_age),
            source_path=str(rollout_path),
            summary="F review, AI gate, production-line, and rollout readiness proof is readable from outside.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Readiness proof only; no AI gate apply, no review publish, no scanner stage run, no rollout enablement, and no F061 run.",
        )
    ]


def _f_production_line_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "F" / "price_list_manager" / "live" / "production_line_health.csv"
    rows = read_csv_rows(path)
    latest = _latest_csv_row(rows)
    age_status, age = _file_status_for_age(path, now, warn_hours=F_REVIEW_WARN_HOURS, fail_hours=F_REVIEW_FAIL_HOURS)
    latest_status = str(latest.get("status", "")).strip().lower()

    if not path.exists() or not rows:
        status = "warn"
        value = "missing"
        root_cause = "F production-line health proof is missing or empty."
        manager_action = "Keep this as missing proof; do not run scanner stages from MOT."
    elif latest_status == "fail":
        status = "fail"
        value = latest.get("value", "fail")
        root_cause = str(latest.get("notes", "")) or "Production-line stage health reports failure."
        manager_action = "Create a manager task for the failing stage handoff proof."
    elif latest_status == "warn":
        status = "warn"
        value = latest.get("value", "warn")
        root_cause = str(latest.get("notes", "")) or "Production-line stage health reports a warning."
        manager_action = "Classify the warning before treating stage proof as complete."
    elif age_status == "fail":
        status = "fail"
        value = "stale"
        root_cause = "F production-line health proof is too stale to trust."
        manager_action = "Refresh stage proof at a safe boundary."
    elif age_status == "warn":
        status = "warn"
        value = "stale"
        root_cause = "F production-line health proof is readable but stale."
        manager_action = "Refresh stage proof at a safe boundary."
    else:
        status = "ok"
        value = latest.get("value", "ok")
        root_cause = ""
        manager_action = "No action; production-line proof is readable."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_production_line_stage_health",
            status=status,
            severity=_severity(status),
            value=value,
            producer="FPM180_build_production_line_run.py",
            expected_output="out/systems/F/price_list_manager/live/production_line_health.csv",
            actual_proof=f"exists={1 if path.exists() else 0};rows={len(rows)};latest_status={latest_status};age_hours={_age_text(age)}",
            age_hours=_age_text(age),
            row_count=str(len(rows)) if rows else "",
            source_path=str(path),
            summary="F production-line stage health is readable and not reporting broken handoffs.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Production-line proof only; no scanner stage run, queue edit, or output deletion.",
        )
    ]


def _f_manager_registration_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "M" / "self_organisation" / "latest_f_script_registration_report.csv"
    rows = read_csv_rows(path)
    required = {
        "scripts/flows/F/F005_build_supplier_price_list_universal.py",
        "scripts/flows/F/F010_build_feeder_candidate_intake.py",
        "scripts/flows/F/F020_build_feeder_candidate_classification.py",
        "scripts/flows/F/F030_build_shared_feeder_pass_logic.py",
        "scripts/flows/F/F040_build_feeder_candidate_approval_queue.py",
        "scripts/flows/F/F050_build_feeder_po_handoff.py",
        "scripts/flows/F/F060_build_legacy_sheet_review_pack.py",
        "scripts/flows/F/F070_build_backtest_policy_snapshot.py",
        "scripts/flows/F/F071_build_backtest_input_view.py",
        "scripts/flows/F/F072_run_backtest_replay.py",
        "scripts/flows/F/F073_build_backtest_summary.py",
        "scripts/flows/F/F074_build_backtest_health.py",
        "scripts/flows/F/F075_apply_backtest_policy_updates.py",
        "scripts/flows/F/F080_build_feedback_calibration_shadow.py",
        "scripts/flows/F/F090_build_amazon_listing_intake.py",
        "scripts/flows/F/F091_reserve_amazon_listing_skus.py",
        "scripts/flows/F/F092_build_amazon_listing_drafts.py",
        "scripts/flows/F/F093_run_amazon_listing_preview.py",
        "scripts/flows/F/F094_submit_amazon_listing_drafts.py",
        "scripts/flows/F/F095_check_amazon_listing_submission_status.py",
        "scripts/flows/F/F096_reconcile_amazon_listing_submissions.py",
        "scripts/flows/F/F097_check_amazon_listing_restrictions.py",
        "scripts/flows/F/F098_build_brand_approval_queue.py",
        "scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py",
        "scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py",
        "scripts/flows/F/price_list_manager/FPM012_enrich_batch_rows_for_f061.py",
        "scripts/flows/F/price_list_manager/FPM013_download_ready_url_sources.py",
        "scripts/flows/F/price_list_manager/FPM014_fetch_api_sources.py",
        "scripts/flows/F/price_list_manager/FPM015_fetch_google_sheet_sources.py",
        "scripts/flows/F/price_list_manager/FPM016_fetch_gmail_email_sources.py",
        "scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py",
        "scripts/flows/F/price_list_manager/FPM030_update_memory_from_results.py",
        "scripts/flows/F/price_list_manager/FPM040_build_next_action.py",
        "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
        "scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py",
        "scripts/flows/F/price_list_manager/FPM080_set_queue_control.py",
        "scripts/flows/F/price_list_manager/FPM090_set_f061_handoff_approval.py",
        "scripts/flows/F/price_list_manager/FPM100_apply_f061_handoff.py",
        "scripts/flows/F/price_list_manager/FPM110_run_test_mode_cycle.py",
        "scripts/flows/F/price_list_manager/FPM120_build_f061_live_trial_samples.py",
        "scripts/flows/F/price_list_manager/FPM121_apply_f061_live_trial_supplier.py",
        "scripts/flows/F/price_list_manager/FPM125_import_f061_recovery_progress.py",
        "scripts/flows/F/price_list_manager/FPM126_update_memory_from_f061_results.py",
        "scripts/flows/F/price_list_manager/FPM140_check_review_handoff_ready.py",
        "scripts/flows/F/price_list_manager/FPM150_build_completed_review_pack.py",
        "scripts/flows/F/price_list_manager/FPM155_apply_review_intelligence_gate.py",
        "scripts/flows/F/price_list_manager/FPM156_build_ai_gate_quality_report.py",
        "scripts/flows/F/price_list_manager/FPM157_build_incremental_ai_precheck.py",
        "scripts/flows/F/price_list_manager/FPM158_ai_precheck_common.py",
        "scripts/flows/F/price_list_manager/FPM160_f061_visible_login_maintenance.py",
        "scripts/flows/F/price_list_manager/FPM180_build_production_line_run.py",
        "scripts/flows/F/price_list_manager/FPM190_build_split_rollout_readiness.py",
        "scripts/flows/F/price_list_manager/FPM191_backfill_ai_quality_stamps.py",
        "scripts/flows/F/F062_reset_supplier_test_mode.py",
        "scripts/flows/F/price_list_manager/FPM001_build_test_fixtures.py",
        "run_F_price_list_manager_cycle.bat",
        "run_F_shure_test_mode_scan_once.bat",
        "run_F_supplier_test_mode_scan_once.bat",
        "run_F_shure_full_legacy_scan.bat",
        "run_F_supplier_full_legacy_scan.bat",
    }
    registered = {
        row.get("script_path", "")
        for row in rows
        if row.get("script_path", "") in required and row.get("classification", "") == "registered" and not row.get("missing_fields", "")
    }
    missing = sorted(required - registered)
    if not path.exists() or not rows:
        status = "warn"
        value = "missing_report"
        root_cause = "F script registration report is missing."
        manager_action = "Refresh the read-only manager front door to rebuild registration proof."
    elif missing:
        status = "warn"
        value = str(len(missing))
        root_cause = "The F manager manifest coverage batch is not fully registered, including control, source, review, and rollout proof steps."
        manager_action = "Register or explicitly classify the missing F manager manifests before calling F complete."
    else:
        status = "ok"
        value = str(len(required))
        root_cause = ""
        manager_action = "No action; the F manager manifest coverage batch, including source-intake proof, is registered."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="F",
            check="f_manager_registration_coverage",
            status=status,
            severity=_severity(status),
            value=value,
            producer="sellerone_manager.self_organisation",
            expected_output="out/systems/M/self_organisation/latest_f_script_registration_report.csv",
            actual_proof=f"exists={1 if path.exists() else 0};rows={len(rows)};registered_required={len(registered)};missing={';'.join(missing)}",
            row_count=str(len(rows)) if rows else "",
            source_path=str(path),
            summary="The F manager manifest coverage batch, including source, control, review, and rollout proof, is registered for outside management.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Manager manifest proof only; no worker script edits or scanner run.",
        )
    ]


def build_f_hourly_mot(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    rows: list[dict[str, str]] = []

    rows.extend(_f_manager_snapshot_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_live_owner_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_child_heartbeat_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_bbp_iframe_plugin_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_storage_drift_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_source_intake_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_url_source_download_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_email_price_list_source_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_queue_recommendation_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_login_mode_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_bbp_account_login_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_seller_central_eligibility_auth_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_visible_login_control_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_queue_handoff_control_rows(base=base, observed_utc=observed))
    rows.extend(_f_rescan_priority_rows(base=base, observed_utc=observed))
    rows.extend(_f_parked_decision_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_recovery_progress_rows(base=base, observed_utc=observed))
    rows.extend(_f_review_handoff_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_review_ai_production_readiness_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_production_line_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_f_manager_registration_rows(base=base, observed_utc=observed))
    return _result_from_rows(observed, "F", rows)


def _o_truthy(value: object) -> bool:
    return _mot_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _o_num(value: object) -> float | None:
    text = _mot_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _o_stage_map_rows(*, observed_utc: str) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    for _feature, stage in O_FEATURE_STAGES:
        counts[stage] = counts.get(stage, 0) + 1
    stage_counts = ";".join(f"{stage}={counts[stage]}" for stage in sorted(counts))
    feature_map = ";".join(f"{feature}:{stage}" for feature, stage in O_FEATURE_STAGES)
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_mid_build_stage_map",
            status="ok",
            severity="info",
            value=stage_counts,
            producer="sellerone_manager O blueprint",
            expected_output="O feature classes are explicit: built, bridge, proof_only, not_started, not_verified, unsafe_blocker",
            actual_proof=feature_map,
            source_path="project_control/EXPECTATIONS/operations_loop_expectations.md",
            summary="O is managed as a construction site, not as a finished live operations loop.",
            manager_action="No action; missing future stages are tracked without calling O broken.",
            safe_repair_boundary="Manager classification only; no O worker run or downstream action.",
        )
    ]


def _o_output_group_row(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    check: str,
    outputs: list[tuple[str, str, str, int]],
    missing_status: str,
    summary: str,
    manager_action_ok: str,
    safe_repair_boundary: str,
    freshness: bool,
) -> dict[str, str]:
    missing: list[str] = []
    short: list[str] = []
    stale_warn: list[str] = []
    stale_fail: list[str] = []
    unreadable: list[str] = []
    row_counts: list[str] = []
    source_paths: list[str] = []
    stages_by_name: dict[str, str] = {}
    max_age: float | None = None

    for name, rel_path, _stage, min_rows in outputs:
        path = base / rel_path
        stages_by_name[name] = _stage
        source_paths.append(str(path))
        if not path.exists():
            missing.append(name)
            continue
        headers = csv_headers(path)
        if headers is None:
            unreadable.append(name)
            continue
        count = csv_row_count(path)
        if count is None:
            unreadable.append(name)
            continue
        row_counts.append(f"{name}:{count}")
        if count < min_rows:
            short.append(f"{name}:{count}/{min_rows}")
        if freshness:
            age_status, age = _file_status_for_age(path, now, warn_hours=O_PROOF_WARN_HOURS, fail_hours=O_PROOF_FAIL_HOURS)
            if age is not None:
                max_age = age if max_age is None else max(max_age, age)
            if age_status == "fail":
                stale_fail.append(name)
            elif age_status == "warn":
                stale_warn.append(name)

    if unreadable or stale_fail or (missing_status == "fail" and missing) or short:
        status = "fail"
        root_cause = "One or more built O proof files are missing, unreadable, too short, or stale."
        manager_action = "Create a bounded O manager-proof repair task. Do not run O worker actions or patch outputs to hide the gap."
    elif missing:
        status = missing_status
        root_cause = "Some proof-only O files are not present yet." if missing_status == "not_checked" else "Some O proof files are missing."
        manager_action = "Keep the missing proof visible as not started or not verified; do not create downstream actions from MOT."
    elif stale_warn:
        status = "warn"
        root_cause = "One or more O proof files are getting old."
        local_refresh_candidates = [
            name for name in stale_warn if stages_by_name.get(name) == "built"
        ]
        bridge_stale = [
            name for name in stale_warn if stages_by_name.get(name) == "bridge"
        ]
        proof_only_stale = [
            name for name in stale_warn if stages_by_name.get(name) == "proof_only"
        ]
        action_parts: list[str] = []
        if local_refresh_candidates:
            action_parts.append(
                "local_refresh_candidates=" + ",".join(local_refresh_candidates)
            )
        if bridge_stale:
            action_parts.append(
                "bridge_stale_labelled=" + ",".join(bridge_stale)
            )
        if proof_only_stale:
            action_parts.append(
                "proof_only_stale=" + ",".join(proof_only_stale)
            )
        manager_action = (
            "Refresh only native built files through an approved local O proof path; "
            "keep bridge and proof-only files labelled instead of pretending they are native O truth."
        )
        if action_parts:
            manager_action = f"{manager_action} {';'.join(action_parts)}"
    else:
        status = "ok"
        root_cause = ""
        manager_action = manager_action_ok

    stale_classification = [
        f"{name}:{stages_by_name.get(name, 'unknown')}"
        for name in stale_warn
    ]
    value_parts = [
        f"missing={len(missing)}",
        f"short={len(short)}",
        f"unreadable={len(unreadable)}",
        f"stale_warn={len(stale_warn)}",
        f"stale_fail={len(stale_fail)}",
    ]
    return mot_row(
        observed_utc=observed_utc,
        flow="O",
        check=check,
        status=status,
        severity=_severity(status),
        value=";".join(value_parts),
        producer="O manager proof map",
        expected_output=";".join(rel_path for _name, rel_path, _stage, _min_rows in outputs),
        actual_proof=(
            f"rows={','.join(row_counts)};missing={','.join(missing)};short={','.join(short)};"
            f"unreadable={','.join(unreadable)};stale_warn={','.join(stale_warn)};"
            f"stale_fail={','.join(stale_fail)};"
            f"stale_classification={','.join(stale_classification)}"
        ),
        age_hours=_age_text(max_age),
        row_count=str(sum(int(part.rsplit(':', 1)[1]) for part in row_counts)) if row_counts else "",
        source_path=";".join(source_paths),
        summary=summary,
        root_cause_guess=root_cause,
        manager_action=manager_action,
        safe_repair_boundary=safe_repair_boundary,
    )


def _o_proof_file_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    return [
        _o_output_group_row(
            base=base,
            observed_utc=observed_utc,
            now=now,
            check="o_active_restock_proof_files",
            outputs=O_ACTIVE_PROOF_OUTPUTS,
            missing_status="fail",
            summary="O's current foundation, bridge, price-proof, and market-refresh files exist; freshness warnings stay visible without blocking user walkthrough proof.",
            manager_action_ok="No action; O's active mid-build proof files are readable.",
            safe_repair_boundary="O proof-file mapping only; no worker run, no H pause, no Sheet write, no purchase action.",
            freshness=True,
        ),
        _o_output_group_row(
            base=base,
            observed_utc=observed_utc,
            now=now,
            check="o_downstream_contract_files",
            outputs=O_DOWNSTREAM_PROOF_OUTPUTS,
            missing_status="not_checked",
            summary="PO, receiving, and send-to-Amazon proof files are contract evidence only until the full loop is proven.",
            manager_action_ok="No action; downstream contract files are present without claiming O is complete.",
            safe_repair_boundary="Contract proof only; no PO creation, receiving action, send-to-Amazon action, or output deletion.",
            freshness=False,
        ),
    ]


def _o_refund_restock_confidence_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "O" / "live" / "restock_source_view.csv"
    rows = read_csv_rows(path)
    headers = csv_headers(path) or []
    required = {
        "expected_refund_cost_per_unit_gbp",
        "refund_unit_rate_30d",
        "refund_unit_rate_90d",
        "refund_units_30d",
        "sales_units_30d",
        "refund_cost_basis",
        "refund_proof_state",
        "refund_sample_confidence",
        "expected_inbound_cost_per_unit_gbp",
        "inbound_cost_basis",
        "inbound_cost_confidence",
        "inbound_cost_source_asof",
        "profit_input_confidence",
        "profit_input_blockers",
    }
    missing = sorted(required - set(headers))
    weak_refund_states = {"", "missing", "unknown", "weak", "not_yet_proven", "sellerboard_bridge_only", "bridge_labelled_only"}
    weak_refund_confidence = {"", "missing", "unknown", "weak", "not_yet_proven"}
    weak_inbound_states = {"", "missing", "unknown", "weak", "not_yet_proven", "missing_inbound_cost_confidence", "unsupported_currency"}
    weak_profit_states = {"", "missing_profit_inputs", "weak_profit_inputs", "unknown", "not_yet_proven"}
    minimum_rows = [row for row in rows if str(row.get("has_minimum_restock_inputs", "")).strip() == "1"]
    weak_refund_rows = [
        row.get("seller_sku", "").strip()
        for row in minimum_rows
        if str(row.get("refund_proof_state", "")).strip().lower() in weak_refund_states
        or str(row.get("refund_sample_confidence", "")).strip().lower() in weak_refund_confidence
    ]
    weak_inbound_rows = [
        row.get("seller_sku", "").strip()
        for row in minimum_rows
        if str(row.get("inbound_cost_confidence", "")).strip().lower() in weak_inbound_states
    ]
    weak_profit_rows = [
        row.get("seller_sku", "").strip()
        for row in minimum_rows
        if str(row.get("profit_input_confidence", "")).strip().lower() in weak_profit_states
    ]
    weak_rows = sorted(set(weak_refund_rows) | set(weak_inbound_rows) | set(weak_profit_rows))
    if not path.exists() or not rows:
        status = "not_checked"
        value = "waiting_for_restock_source_view"
        root = "O expected-profit input confidence waits until the restock source view exists."
    elif missing:
        status = "not_checked"
        value = f"missing_profit_input_columns={len(missing)}"
        root = "O restock source view does not yet carry refund, inbound, and profit-input confidence fields."
    elif weak_rows:
        status = "warn"
        value = (
            f"minimum_input_rows_with_weak_profit_inputs={len(weak_rows)};"
            f"refund={len(set(weak_refund_rows))};"
            f"inbound={len(set(weak_inbound_rows))};"
            f"profit={len(set(weak_profit_rows))}"
        )
        root = "Some O restock input rows still have weak expected-profit proof labels."
    else:
        status = "ok"
        value = "profit_input_confidence_fields_present"
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_refund_restock_confidence_fields",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O001_build_restock_source_view.py",
            expected_output="O restock source view carries refund drag, inbound/FBA cost drag, proof-state, and combined profit-input confidence fields",
            actual_proof=(
                f"exists={1 if path.exists() else 0};"
                f"rows={len(rows)};"
                f"missing_columns={';'.join(missing)};"
                f"minimum_input_rows_with_weak_profit_inputs={len(weak_rows)};"
                f"weak_refund_rows={len(set(weak_refund_rows))};"
                f"weak_inbound_rows={len(set(weak_inbound_rows))};"
                f"weak_profit_rows={len(set(weak_profit_rows))}"
            ),
            row_count=str(len(rows)),
            source_path=str(path),
            summary="O should display expected-profit inputs with proof labels so weak refund or inbound/FBA cost proof cannot silently look business-ready.",
            root_cause_guess=root,
            manager_action="Refresh or repair O source view expected-profit confidence fields before using restocking profit as business-ready.",
            safe_repair_boundary="O expected-profit confidence proof only; no purchase, PO, receiving, send-to-Amazon, Sheet, price, queue, DB alignment, output deletion, or restock decision.",
        )
    ]


def _o_inbound_fba_cost_proof_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "O" / "live" / "restock_inbound_fba_cost_proof_live.csv"
    rows = read_csv_rows(path)

    def _int(value: object) -> int:
        try:
            return int(float(str(value or "").strip()))
        except ValueError:
            return 0

    by_check = {
        str(row.get("check_name", "")).strip(): row
        for row in rows
        if str(row.get("check_name", "")).strip()
    }
    events = by_check.get("inbound_cost_events", {})
    sku_cost = by_check.get("sku_cost_allocation", {})
    restock = by_check.get("restock_source_attachment", {})
    event_rows = _int(events.get("source_rows", ""))
    event_linked_rows = _int(events.get("linked_rows", ""))
    sku_cost_rows = _int(sku_cost.get("linked_rows", ""))
    restock_rows = _int(restock.get("restock_rows", ""))
    restock_safe_rows = _int(restock.get("restock_rows_with_sku_cost", ""))
    restock_missing_rows = _int(restock.get("restock_rows_missing_sku_cost", ""))
    source_paths = sorted(
        {
            str(row.get("source_path", "")).strip()
            for row in rows
            if str(row.get("source_path", "")).strip()
        }
    )

    if not path.exists() or not rows:
        status = "not_checked"
        value = "waiting_for_inbound_fba_cost_proof"
        root = "O inbound/FBA cost allocation proof has not been built yet."
    elif restock_rows and restock_missing_rows == 0 and restock_safe_rows > 0:
        status = "ok"
        value = (
            f"safe_rows={restock_safe_rows};missing_rows=0;"
            f"event_rows={event_rows};event_linked_rows={event_linked_rows};sku_cost_rows={sku_cost_rows}"
        )
        root = ""
    else:
        status = "warn"
        value = (
            f"safe_rows={restock_safe_rows};missing_rows={restock_missing_rows};"
            f"event_rows={event_rows};event_linked_rows={event_linked_rows};sku_cost_rows={sku_cost_rows}"
        )
        root = "O has no safe SKU-level inbound/FBA cost allocation for one or more restock rows."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_inbound_fba_cost_allocation_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O022_build_inbound_fba_cost_proof.py",
            expected_output="O has read-only proof showing whether inbound/FBA cost can be safely attached to restock rows.",
            actual_proof=(
                f"exists={1 if path.exists() else 0};"
                f"proof_rows={len(rows)};"
                f"event_rows={event_rows};"
                f"event_linked_rows={event_linked_rows};"
                f"sku_cost_rows={sku_cost_rows};"
                f"restock_rows={restock_rows};"
                f"restock_rows_with_sku_cost={restock_safe_rows};"
                f"restock_rows_missing_sku_cost={restock_missing_rows}"
            ),
            row_count=str(restock_rows or len(rows)),
            source_path=";".join([str(path), *source_paths]),
            summary="O should keep expected profit blocked when inbound/FBA cost rows cannot be traced to SKU-level cost proof.",
            root_cause_guess=root,
            manager_action="Build or repair only read-only inbound/FBA cost proof. Do not guess costs or use unlinked fees as profit-safe values.",
            safe_repair_boundary="O inbound/FBA cost proof only; no purchase, PO, receiving, send-to-Amazon, Sheet, price, queue, DB alignment, output deletion, or restock decision.",
        )
    ]


def _o_profit_input_blocker_breakdown_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "O" / "live" / "restock_profit_input_blocker_breakdown_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_profit_input_blocker_breakdown_health.csv"
    rows = read_csv_rows(path)
    health_rows = read_csv_rows(health_path)

    def _int(value: object) -> int:
        try:
            return int(float(str(value or "").strip()))
        except ValueError:
            return 0

    def _value_parts(value: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in str(value or "").split(";"):
            key, sep, val = part.partition("=")
            if sep:
                out[key.strip()] = val.strip()
        return out

    health_by_check = {
        str(row.get("check", "")).strip(): row
        for row in health_rows
        if str(row.get("check", "")).strip()
    }
    summary = health_by_check.get("profit_input_blocker_rows", {})
    lanes = health_by_check.get("weak_input_lanes", {})
    summary_parts = _value_parts(str(summary.get("value", "")))
    lane_parts = _value_parts(str(lanes.get("value", "")))
    minimum_rows = _int(summary_parts.get("minimum_input_rows", ""))
    weak_rows = _int(summary_parts.get("weak_rows", "")) if summary_parts else len(rows)
    refund_rows = _int(lane_parts.get("refund", ""))
    inbound_rows = _int(lane_parts.get("inbound", ""))
    profit_rows = _int(lane_parts.get("profit", ""))
    token_cost_rows = _int(lane_parts.get("token_cost", ""))
    unsafe_clean_buy = [
        row.get("seller_sku", "").strip() or row.get("asin", "").strip() or "missing_row"
        for row in rows
        if str(row.get("safe_for_clean_buy", "")).strip() != "0"
        or str(row.get("safe_for_po", "")).strip() != "0"
        or str(row.get("needs_luke_decision", "")).strip() not in {"", "0"}
    ]
    missing_primary = [
        row.get("seller_sku", "").strip() or row.get("asin", "").strip() or "missing_row"
        for row in rows
        if not str(row.get("primary_blocker", "")).strip()
    ]

    if not path.exists() or not health_path.exists() or not health_rows:
        status = "not_checked"
        value = "waiting_for_profit_input_blocker_breakdown"
        root = "O profit-input blocker breakdown has not been built yet."
        manager_action = "Build the read-only O023 profit-input blocker breakdown. Do not guess costs or open buying."
    elif unsafe_clean_buy:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_clean_buy)}"
        root = "A profit-input blocker row claims a clean buy, PO, or Luke decision is allowed."
        manager_action = "Repair the blocker breakdown safety labels before using Restock Session proof."
    elif missing_primary:
        status = "fail"
        value = f"missing_primary_blocker={len(missing_primary)}"
        root = "A profit-input blocker row does not explain its primary blocker."
        manager_action = "Repair O023 blocker classification before using the proof output."
    elif weak_rows:
        status = "warn"
        value = (
            f"minimum_input_rows={minimum_rows};weak_rows={weak_rows};"
            f"refund={refund_rows};inbound={inbound_rows};profit={profit_rows};token_cost={token_cost_rows}"
        )
        root = "O has rows with basic restock inputs, but expected profit is still blocked by weak proof."
        manager_action = "Keep these rows blocked and use the breakdown to decide the next safe proof lane."
    else:
        status = "ok"
        value = f"minimum_input_rows={minimum_rows};weak_rows=0"
        root = ""
        manager_action = "No action; no minimum-input rows have weak expected-profit proof."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_profit_input_blocker_breakdown",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O023_build_profit_input_blocker_breakdown.py",
            expected_output="O has a read-only row-level breakdown for weak expected-profit inputs.",
            actual_proof=(
                f"exists={1 if path.exists() else 0};"
                f"health_exists={1 if health_path.exists() else 0};"
                f"rows={len(rows)};health_rows={len(health_rows)};"
                f"unsafe_clean_buy={len(unsafe_clean_buy)};"
                f"missing_primary_blocker={len(missing_primary)};"
                f"unsafe_rows={','.join(unsafe_clean_buy)};"
                f"missing_primary_rows={','.join(missing_primary)}"
            ),
            row_count=str(len(rows)),
            source_path=f"{path};{health_path}",
            summary="O should show exactly why expected restock profit is still not clean before any approval or PO step.",
            root_cause_guess=root,
            manager_action=manager_action,
            safe_repair_boundary="O profit-input blocker proof only; no purchase, PO, receiving, send-to-Amazon, Sheet, price, queue, DB alignment, output deletion, cost guessing, or restock decision.",
        )
    ]


def _o_inbound_fba_source_options_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "O" / "live" / "restock_inbound_fba_source_options_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_inbound_fba_source_options_health.csv"
    rows = read_csv_rows(path)
    health_rows = read_csv_rows(health_path)

    def _int(value: object) -> int:
        try:
            return int(float(str(value or "").strip()))
        except ValueError:
            return 0

    def _parts(value: object) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in str(value or "").split(";"):
            key, sep, val = part.partition("=")
            if sep:
                out[key.strip()] = val.strip()
        return out

    by_check = {
        str(row.get("check", "")).strip(): row
        for row in health_rows
        if str(row.get("check", "")).strip()
    }
    direct_summary = _parts(by_check.get("direct_safe_routes", {}).get("value", ""))
    direct_safe = _int(direct_summary.get("direct_safe_routes", ""))
    protected_routes = _int(direct_summary.get("protected_routes", ""))
    unsafe_protected_clean = [
        row.get("route_id", "").strip() or "missing_route"
        for row in rows
        if str(row.get("route_class", "")).strip().startswith("protected")
        and str(row.get("safe_for_profit_use", "")).strip() != "0"
    ]
    unsafe_direct_clean = [
        row.get("route_id", "").strip() or "missing_route"
        for row in rows
        if str(row.get("route_class", "")).strip() == "direct"
        and str(row.get("safe_for_profit_use", "")).strip() == "1"
        and str(row.get("linked_rows", "")).strip() in {"", "0"}
    ]

    if not path.exists() or not health_path.exists() or not health_rows:
        status = "not_checked"
        value = "waiting_for_inbound_fba_source_options"
        root = "O inbound/FBA source-options review has not been built yet."
        manager_action = "Build the read-only O024 source-options review. Do not fetch, estimate, or choose a policy."
    elif unsafe_protected_clean or unsafe_direct_clean:
        status = "fail"
        value = f"unsafe_protected_clean={len(unsafe_protected_clean)};unsafe_direct_clean={len(unsafe_direct_clean)}"
        root = "An inbound/FBA source route is being treated as clean without safe direct proof."
        manager_action = "Repair O024 source-route classification before using inbound/FBA profit proof."
    elif direct_safe:
        status = "ok"
        value = f"direct_safe_routes={direct_safe};protected_routes={protected_routes}"
        root = ""
        manager_action = "Use the direct safe route in the next bounded local proof step."
    else:
        status = "warn"
        value = f"direct_safe_routes=0;protected_routes={protected_routes}"
        root = "No existing local direct inbound/FBA cost route is safe for O profit proof."
        manager_action = "Keep O blocked. A protected policy, source repair, or live fetch would need Luke before use."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_inbound_fba_source_options",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O024_build_inbound_fba_source_options.py",
            expected_output="O classifies local inbound/FBA cost proof routes before using any route in expected restock profit.",
            actual_proof=(
                f"exists={1 if path.exists() else 0};"
                f"health_exists={1 if health_path.exists() else 0};"
                f"route_rows={len(rows)};health_rows={len(health_rows)};"
                f"unsafe_protected_clean={len(unsafe_protected_clean)};"
                f"unsafe_direct_clean={len(unsafe_direct_clean)};"
                f"unsafe_protected_routes={','.join(unsafe_protected_clean)};"
                f"unsafe_direct_routes={','.join(unsafe_direct_clean)}"
            ),
            row_count=str(len(rows)),
            source_path=f"{path};{health_path}",
            summary="O should know whether inbound/FBA cost proof can be solved locally or must stay parked behind a protected source choice.",
            root_cause_guess=root,
            manager_action=manager_action,
            safe_repair_boundary="O inbound/FBA source-options proof only; no Amazon fetch, cost estimate, policy choice, purchase, PO, receiving, send-to-Amazon, Sheet, price, queue, DB alignment, output deletion, or source rewrite.",
        )
    ]


def _o_token_cost_trust_gate_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "O" / "live" / "restock_token_cost_trust_gate_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_token_cost_trust_gate_health.csv"
    coverage_path = base / "out" / "systems" / "O" / "live" / "reorder_input_coverage_report.csv"
    session_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    rows = read_csv_rows(path)
    health_rows = read_csv_rows(health_path)
    coverage_rows = read_csv_rows(coverage_path)
    session_rows = read_csv_rows(session_path)

    def _state(row: dict[str, str]) -> str:
        return _mot_text(row.get("token_cost_trust_state", "")).lower()

    untrusted_rows = [
        row.get("seller_sku", "").strip() or "missing_sku"
        for row in rows
        if _state(row) != "trusted"
    ]
    unsafe_gate_rows = [
        row.get("seller_sku", "").strip() or "missing_sku"
        for row in rows
        if _state(row) != "trusted"
        and (_o_truthy(row.get("safe_for_clean_buy", "")) or _o_truthy(row.get("safe_for_po", "")))
    ]
    unsafe_coverage_rows = [
        row.get("seller_sku", "").strip() or "missing_sku"
        for row in coverage_rows
        if _o_truthy(row.get("action_ready_now", ""))
        and _mot_text(row.get("token_cost_trust_state", "")).lower() != "trusted"
    ]
    unsafe_session_rows = [
        row.get("seller_sku", "").strip() or "missing_sku"
        for row in session_rows
        if _mot_text(row.get("token_cost_trust_state", "")).lower() != "trusted"
        and _mot_text(row.get("action_safety_state", "")).lower() not in {"", "blocked_from_clean_buy"}
    ]
    missing_state_rows = [
        row.get("seller_sku", "").strip() or "missing_sku"
        for row in rows
        if not _state(row)
    ]

    if not path.exists() or not health_path.exists() or not health_rows:
        status = "not_checked"
        value = "waiting_for_token_cost_trust_gate"
        root = "O token-cost trust gate has not been built yet."
        manager_action = "Build O025 read-only token-cost trust proof before using token cost in restock profit."
    elif unsafe_gate_rows or unsafe_coverage_rows or unsafe_session_rows:
        status = "fail"
        value = (
            f"unsafe_gate_rows={len(unsafe_gate_rows)};"
            f"unsafe_action_ready_rows={len(unsafe_coverage_rows)};"
            f"unsafe_session_rows={len(unsafe_session_rows)}"
        )
        root = "O is allowing token cost to influence buy readiness without trusted token-cost proof."
        manager_action = "Repair O token-cost trust propagation before using Restock Session for clean-buy decisions."
    elif missing_state_rows:
        status = "fail"
        value = f"missing_token_cost_trust_state={len(missing_state_rows)}"
        root = "O token-cost trust rows are missing their trust-state label."
        manager_action = "Repair O025 token-cost trust classification."
    elif untrusted_rows:
        status = "warn"
        value = f"rows={len(rows)};untrusted_rows={len(untrusted_rows)}"
        root = "Some O rows cannot yet trust token cost for clean expected-profit proof."
        manager_action = "Keep affected rows blocked from clean buy until B fallback-cost proof is trusted."
    else:
        status = "ok"
        value = f"rows={len(rows)};untrusted_rows=0"
        root = ""
        manager_action = "No action; O token-cost trust gate is clean."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_token_cost_trust_gate",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O025_build_token_cost_trust_gate.py",
            expected_output="O has read-only proof that token cost is trusted before expected profit becomes clean.",
            actual_proof=(
                f"exists={1 if path.exists() else 0};"
                f"health_exists={1 if health_path.exists() else 0};"
                f"rows={len(rows)};health_rows={len(health_rows)};"
                f"untrusted_rows={len(untrusted_rows)};"
                f"unsafe_gate_rows={len(unsafe_gate_rows)};"
                f"unsafe_action_ready_rows={len(unsafe_coverage_rows)};"
                f"unsafe_session_rows={len(unsafe_session_rows)};"
                f"missing_state_rows={len(missing_state_rows)}"
            ),
            row_count=str(len(rows)),
            source_path=f"{path};{health_path};{coverage_path};{session_path}",
            summary="O should not treat SKU token cost as clean profit proof when B fallback-cost evidence is weak or missing.",
            root_cause_guess=root,
            manager_action=manager_action,
            safe_repair_boundary="O token-cost trust proof only; no token correction, purchase, PO, receiving, send-to-Amazon, Sheet, price, queue, DB alignment, output deletion, or business decision.",
        )
    ]


def _o_buy_guardrail_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    path = base / "out" / "systems" / "O" / "live" / "reorder_input_coverage_report.csv"
    rows = read_csv_rows(path)
    if not path.exists() or not rows:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="O",
                check="o_buy_ready_guardrails",
                status="fail",
                severity="blocker",
                value="coverage_missing",
                producer="O020_build_reorder_input_coverage_report.py",
                expected_output="out/systems/O/live/reorder_input_coverage_report.csv",
                actual_proof=f"exists={1 if path.exists() else 0};rows={len(rows)}",
                source_path=str(path),
                summary="O cannot prove buy-ready safety without the reorder coverage report.",
                root_cause_guess="O buy guardrail proof is missing.",
                manager_action="Restore O020 proof before approving any buy-ready path.",
                safe_repair_boundary="O020 proof only; no purchase, queue, Sheet, DB, or price action.",
            )
        ]

    action_ready_rows = [row for row in rows if _o_truthy(row.get("action_ready_now", ""))]
    unsafe: list[str] = []
    for row in action_ready_rows:
        sku = _mot_text(row.get("seller_sku", "")) or _mot_text(row.get("asin", "")) or "unknown"
        reasons: list[str] = []
        if not _o_truthy(row.get("has_current_cost_input", "")):
            reasons.append("missing_cost")
        if not _o_truthy(row.get("has_current_market_price_input", "")):
            reasons.append("missing_market")
        if _mot_text(row.get("net_fee_model_status", "")).lower() != "fresh":
            reasons.append("net_fee_not_fresh")
        max_safe = _o_num(row.get("max_safe_unit_cost_gbp", "")) or _o_num(row.get("max_target_roi_purchase_price_gbp", ""))
        if max_safe is None or max_safe <= 0:
            reasons.append("max_pay_missing")
        if _mot_text(row.get("purchase_price_safety_status", "")).lower() != "within_target_roi_max":
            reasons.append("not_within_target_roi_max")
        if reasons:
            unsafe.append(f"{sku}:{'|'.join(reasons)}")

    status = "fail" if unsafe else "ok"
    value = "no_action_ready" if not action_ready_rows else f"action_ready={len(action_ready_rows)};unsafe={len(unsafe)}"
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_buy_ready_guardrails",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O020_build_reorder_input_coverage_report.py",
            expected_output="No buy-ready row unless cost, market proof, net-fee proof, and Max pay are safe.",
            actual_proof=f"rows={len(rows)};action_ready={len(action_ready_rows)};unsafe={';'.join(unsafe[:20])}",
            row_count=str(len(rows)),
            source_path=str(path),
            summary="O blocks buy-ready status unless the key safety proofs are present.",
            root_cause_guess="At least one O row is buy-ready without complete safety proof." if unsafe else "",
            manager_action=(
                "Block purchase-order work and repair the earliest missing proof source."
                if unsafe
                else "No action; current O rows are either blocked or safely ready."
            ),
            safe_repair_boundary="Guardrail proof only; no PO creation, Sheet write, price change, queue edit, or output masking.",
        )
    ]


def _o_legacy_bridge_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    bridge_path = base / "out" / "systems" / "O" / "live" / "legacy_purchase_list_bridge.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "legacy_purchase_list_bridge_health.csv"
    bridge_rows = read_csv_rows(bridge_path)
    health_rows = read_csv_rows(health_path)
    bad_source = [
        row for row in bridge_rows
        if _mot_text(row.get("source_system", "")).lower() != "legacy_purchase_list"
    ]
    done_rows = [row for row in bridge_rows if _o_truthy(row.get("done_flag", ""))]
    bad_health = [
        row for row in health_rows
        if _mot_text(row.get("status", "")).lower() not in {"ok", "not_checked", ""}
    ]
    if not bridge_path.exists() or not health_path.exists():
        status = "fail"
        root_cause = "The legacy Purchase List bridge proof is missing."
        manager_action = "Restore bridge proof or remove bridge claims. Do not write Google Sheets from MOT."
    elif bad_source or done_rows or bad_health:
        status = "fail"
        root_cause = "Legacy bridge rows are not safely labelled or bridge health is not clean."
        manager_action = "Fix the bridge import/source labelling before using bridge rows in the UI."
    else:
        status = "ok"
        root_cause = ""
        manager_action = "No action; bridge rows remain labelled as temporary legacy Purchase List proof."
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_legacy_bridge_source_labels",
            status=status,
            severity=_severity(status),
            value=f"bridge_rows={len(bridge_rows)};bad_source={len(bad_source)};done_rows={len(done_rows)};bad_health={len(bad_health)}",
            producer="O009_build_legacy_purchase_list_bridge.py",
            expected_output="Legacy bridge rows are local-only and labelled source_system=legacy_purchase_list.",
            actual_proof=(
                f"bridge_exists={1 if bridge_path.exists() else 0};health_exists={1 if health_path.exists() else 0};"
                f"bridge_rows={len(bridge_rows)};health_rows={len(health_rows)};bad_source={len(bad_source)};"
                f"done_rows={len(done_rows)};bad_health={len(bad_health)}"
            ),
            row_count=str(len(bridge_rows)) if bridge_rows else "",
            source_path=f"{bridge_path};{health_path}",
            summary="The Sheet-based Purchase List path remains a temporary read-only bridge, not native O truth.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Bridge labelling proof only; no Google Sheets write and no native-truth promotion.",
        )
    ]


def _o_po_source_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    headers_path = base / "out" / "systems" / "O" / "live" / "purchase_orders_live.csv"
    lines_path = base / "out" / "systems" / "O" / "live" / "purchase_order_lines_live.csv"
    holds_path = base / "out" / "systems" / "O" / "live" / "purchase_order_draft_holds.csv"
    header_rows = read_csv_rows(headers_path)
    line_rows = read_csv_rows(lines_path)
    hold_rows = read_csv_rows(holds_path)
    if not headers_path.exists() or not lines_path.exists():
        status = "not_checked"
        root_cause = "PO draft proof files are not present yet."
        manager_action = "Keep PO draft creation as proof-only/not verified until O100 proof files exist."
    else:
        missing_source = []
        source_mix: dict[str, int] = {}
        for row in line_rows:
            source_event = _mot_text(row.get("source_event_id", ""))
            cost_mode = _mot_text(row.get("cost_mode", "")).lower()
            basis = _mot_text(row.get("recommendation_basis", "")).lower()
            source_mix[cost_mode or "blank"] = source_mix.get(cost_mode or "blank", 0) + 1
            if not source_event or not cost_mode or not basis:
                sku = _mot_text(row.get("seller_sku", "")) or _mot_text(row.get("asin", "")) or "unknown"
                missing_source.append(sku)
        status = "fail" if missing_source else "ok"
        root_cause = "At least one PO draft line lacks source labels." if missing_source else ""
        manager_action = (
            "Hold PO use until source labels are repaired."
            if missing_source
            else "No action; PO draft rows are labelled as proof-only source trails."
        )
    mix_text = ",".join(f"{key}:{value}" for key, value in sorted(source_mix.items())) if "source_mix" in locals() else ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_source_separation",
            status=status,
            severity=_severity(status),
            value=f"proof_only;headers={len(header_rows)};lines={len(line_rows)};holds={len(hold_rows)};source_mix={mix_text}",
            producer="O010_apply_restock_decisions.py / O100_build_purchase_orders.py",
            expected_output="PO rows must show source and stay proof-only until native O PO completion is proven.",
            actual_proof=f"headers={len(header_rows)};lines={len(line_rows)};holds={len(hold_rows)};missing_source={','.join(missing_source[:20]) if 'missing_source' in locals() else ''}",
            row_count=str(len(line_rows)) if line_rows else "",
            source_path=f"{headers_path};{lines_path};{holds_path}",
            summary="PO draft evidence is labelled by source, so sample and legacy rows are not mistaken for native O completion.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="PO source proof only; no real PO creation or purchase commitment.",
        )
    ]


def _o_receiving_send_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "purchase_order_lines_live.csv"
    receiving_path = base / "out" / "systems" / "O" / "live" / "receiving_events.csv"
    queue_path = base / "out" / "systems" / "O" / "live" / "send_to_amazon_queue.csv"
    handoff_path = base / "out" / "systems" / "O" / "live" / "send_to_amazon_handoff_log.csv"
    line_rows = read_csv_rows(lines_path)
    receiving_rows = read_csv_rows(receiving_path)
    queue_rows = read_csv_rows(queue_path)
    handoff_rows = read_csv_rows(handoff_path)
    line_ids = {_mot_text(row.get("po_line_id", "")) for row in line_rows if _mot_text(row.get("po_line_id", ""))}
    bad_queue: list[str] = []
    for row in queue_rows:
        line_id = _mot_text(row.get("po_line_id", ""))
        available = _o_num(row.get("received_qty_available_for_send", ""))
        if not line_id or line_id not in line_ids:
            bad_queue.append(f"{line_id or 'missing'}:missing_po_line")
        elif available is None or available <= 0:
            bad_queue.append(f"{line_id}:no_received_qty")
    if queue_rows and bad_queue:
        status = "fail"
        root_cause = "Send-to-Amazon queue has rows without received stock proof."
        manager_action = "Block send-to-Amazon use and repair queue proof at the source."
    else:
        status = "ok"
        root_cause = ""
        manager_action = "No action; send-to-Amazon remains empty or backed by received-stock proof."
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_receiving_send_safety",
            status=status,
            severity=_severity(status),
            value=f"lines={len(line_rows)};receiving={len(receiving_rows)};send_queue={len(queue_rows)};handoff={len(handoff_rows)};bad_queue={len(bad_queue)}",
            producer="O210_apply_receiving_events.py / O300_build_send_to_amazon_queue.py",
            expected_output="Send-to-Amazon rows only appear after approved PO and receiving proof.",
            actual_proof=f"line_ids={len(line_ids)};bad_queue={';'.join(bad_queue[:20])}",
            row_count=str(len(queue_rows)),
            source_path=f"{lines_path};{receiving_path};{queue_path};{handoff_path}",
            summary="Receiving and send-to-Amazon are proof-only until a real approved PO-to-receipt-to-send chain exists.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Receiving/send proof only; no receiving action, no Amazon handoff, no output deletion.",
        )
    ]


def _o_restock_session_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_session_supplier_summary_live.csv"
    reason_path = base / "out" / "systems" / "O" / "live" / "restock_session_reason_codes.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_session_health.csv"
    draft_path = base / "out" / "systems" / "O" / "live" / "restock_session_draft_decision_events.csv"
    review_rows = read_csv_rows(review_path)
    summary_rows = read_csv_rows(summary_path)
    reason_rows = read_csv_rows(reason_path)
    health_rows = read_csv_rows(health_path)
    draft_rows = read_csv_rows(draft_path)
    paths = [review_path, summary_path, reason_path, health_path, draft_path]
    missing = [path.name for path in paths if not path.exists()]
    invalid_source_rows = [
        row.get("seller_sku", "")
        for row in review_rows
        if _mot_text(row.get("source_class", "")) not in {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    ]
    live_action_reasons = [
        row.get("reason_code", "")
        for row in reason_rows
        if _mot_text(row.get("creates_live_action", "")) != "0"
    ]
    buy_ready_claims = [
        row.get("seller_sku", "")
        for row in review_rows
        if "buy_ready" in _mot_text(row.get("action_safety_state", "")).lower()
    ]
    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    allowed_draft_codes = {
        "order_qty_draft",
        "snooze",
        "drop",
        "likely_discontinued",
        "needs_fresh_supplier_scan",
        "backorder_wait",
        "already_ordered_or_paid",
        "awaiting_supplier_shipment",
        "supplier_moq_too_low",
        "profit_too_low",
        "proof_missing",
    }
    bad_draft_rows: list[str] = []
    for row in draft_rows:
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or _mot_text(row.get("draft_id", "")) or "missing_row"
        code = _mot_text(row.get("decision_code", ""))
        qty = _mot_text(row.get("draft_order_qty", ""))
        snooze_until = _mot_text(row.get("snooze_until_utc", ""))
        if _mot_text(row.get("creates_live_action", "")) != "0":
            bad_draft_rows.append(f"{row_label}:creates_live_action")
        elif _mot_text(row.get("draft_status", "")) != "draft":
            bad_draft_rows.append(f"{row_label}:bad_status")
        elif code not in allowed_draft_codes:
            bad_draft_rows.append(f"{row_label}:bad_code")
        elif code == "order_qty_draft":
            try:
                qty_num = float(qty)
            except ValueError:
                qty_num = 0.0
            if qty_num <= 0 or not qty_num.is_integer():
                bad_draft_rows.append(f"{row_label}:bad_qty")
        elif qty:
            bad_draft_rows.append(f"{row_label}:qty_on_non_order_code")
        elif code == "snooze" and not snooze_until:
            bad_draft_rows.append(f"{row_label}:missing_snooze_date")
        elif code != "snooze" and snooze_until:
            bad_draft_rows.append(f"{row_label}:snooze_on_non_snooze_code")
    blocked_rows = sum(1 for row in review_rows if _mot_text(row.get("row_status", "")).lower() == "blocked")
    supplier_count = len({_mot_text(row.get("supplier_name", "")) for row in review_rows if _mot_text(row.get("supplier_name", ""))})

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O restock-session proof files are missing."
        manager_action = "Run the bounded O460 local session builder. Do not create POs, write Sheets, edit queues, change prices, or run market proof."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more restock-session rows do not have an approved source class."
        manager_action = "Repair source labelling in the O session builder before using the UI view."
    elif live_action_reasons:
        status = "fail"
        value = f"live_action_reason_codes={len(live_action_reasons)}"
        root_cause = "A restock-session reason code appears to create a live action."
        manager_action = "Keep O session decisions local-only. Do not connect them to PO or supplier/Amazon actions."
    elif buy_ready_claims:
        status = "fail"
        value = f"buy_ready_claims={len(buy_ready_claims)}"
        root_cause = "The restock-session view is using buy-ready wording."
        manager_action = "Replace buy-ready wording with review-only or blocked wording until the full proof chain exists."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The O restock-session health file contains a non-ok check."
        manager_action = "Repair the O session proof source instead of masking the UI output."
    elif bad_draft_rows:
        status = "fail"
        value = f"bad_draft_rows={len(bad_draft_rows)}"
        root_cause = "A restock-session draft decision is not safe local-only evidence."
        manager_action = "Repair the O draft decision validator before using draft decisions in the UI."
    elif not review_rows:
        status = "warn"
        value = "rows=0"
        root_cause = "The O restock-session view has no rows."
        manager_action = "Keep this visible. Empty rows are not a live-loop failure unless current restock work is expected."
    else:
        status = "ok"
        value = f"rows={len(review_rows)};suppliers={supplier_count};blocked={blocked_rows};summary={len(summary_rows)};drafts={len(draft_rows)}"
        root_cause = ""
        manager_action = "No action; the O restock-session view is local, labelled, and review-only."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_restock_session_readiness",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O460_build_restock_session_view.py",
            expected_output="O restock-session local view, supplier summary, reason codes, and health proof.",
            actual_proof=(
                f"review_exists={1 if review_path.exists() else 0};review_rows={len(review_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"reason_exists={1 if reason_path.exists() else 0};reason_rows={len(reason_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"draft_exists={1 if draft_path.exists() else 0};draft_rows={len(draft_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"live_action_reasons={','.join(live_action_reasons)};buy_ready_claims={','.join(buy_ready_claims)};"
                f"health_bad={','.join(health_bad)};bad_draft_rows={','.join(bad_draft_rows)}"
            ),
            row_count=str(len(review_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O restock-session proof shows one local review lane without live buying actions.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O session proof only; no purchase commitment, PO creation, receiving, send-to-Amazon, "
                "Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_restock_supplier_batch_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_health.csv"
    proof_events_path = base / "out" / "systems" / "O" / "live" / "restock_session_supplier_proof_events.csv"
    pack_moq_events_path = base / "out" / "systems" / "O" / "live" / "restock_session_pack_moq_proof_events.csv"
    lines_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    proof_event_rows = read_csv_rows(proof_events_path)
    pack_moq_event_rows = read_csv_rows(pack_moq_events_path)
    paths = [lines_path, summary_path, health_path, proof_events_path, pack_moq_events_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    allowed_stock_states = {"supplier_stock_verified_in_stock", "supplier_stock_verified_zero", "supplier_stock_not_verified"}
    allowed_backorder_states = {"backorder_none_confirmed", "backorder_wait", "backorder_not_verified"}
    allowed_pack_moq_states = {"pack_moq_verified", "pack_moq_not_verified"}
    allowed_readiness_states = {"blocked_from_purchase_approval", "ready_for_purchase_approval_review_only"}

    def supplier_missing_reasons(row: dict[str, str]) -> list[str]:
        missing: list[str] = []
        supplier_match_state = _mot_text(row.get("supplier_match_state", ""))
        supplier_proof_state = _mot_text(row.get("supplier_proof_state", ""))
        supplier_cost_state = _mot_text(row.get("supplier_cost_proof_state", ""))
        supplier_stock_state = _mot_text(row.get("supplier_stock_state", ""))
        backorder_state = _mot_text(row.get("backorder_state", ""))
        supplier_file_asof = _mot_text(row.get("supplier_file_asof_utc", ""))
        pack_state = _mot_text(row.get("pack_moq_proof_state", ""))
        if supplier_match_state != "exact_supplier_sku_or_barcode_match" or supplier_proof_state != "supplier_exact_match_proved":
            missing.append("exact_supplier_match_not_proved")
        if (
            supplier_cost_state == ""
            or supplier_cost_state.startswith("missing")
            or supplier_cost_state.startswith("bridge")
            or supplier_cost_state.endswith("not_verified")
            or "unknown" in supplier_cost_state
            or supplier_cost_state == "supplier_cost_not_exact"
        ):
            missing.append("supplier_cost_not_proved")
        if supplier_stock_state in {"", "supplier_stock_not_verified"}:
            missing.append("supplier_stock_not_verified")
        if backorder_state in {"", "backorder_not_verified"}:
            missing.append("backorder_not_verified")
        if supplier_file_asof == "":
            missing.append("supplier_file_asof_missing")
        if pack_state in {"", "pack_moq_not_verified"}:
            missing.append("pack_moq_not_verified")
        return missing

    invalid_source_rows: list[str] = []
    bad_qty_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    bad_supplier_clear_rows: list[str] = []
    missing_supplier_reason_rows: list[str] = []
    bad_proof_event_rows: list[str] = []
    bad_pack_moq_event_rows: list[str] = []
    bad_readiness_rows: list[str] = []
    missing_readiness_reason_rows: list[str] = []
    for row in proof_event_rows:
        proof_label = _mot_text(row.get("proof_id", "")) or _mot_text(row.get("row_id", "")) or "missing_proof"
        stock_state = _mot_text(row.get("supplier_stock_state", ""))
        stock_qty_text = _mot_text(row.get("supplier_stock_qty", ""))
        backorder_state = _mot_text(row.get("backorder_state", ""))
        backorder_eta = _mot_text(row.get("backorder_eta_utc", ""))
        supplier_file_asof = _mot_text(row.get("supplier_file_asof_utc", ""))
        proof_status = _mot_text(row.get("proof_status", ""))
        errors: list[str] = []
        if _mot_text(row.get("creates_live_action", "")) != "0":
            errors.append("creates_live_action")
        if proof_status != "draft_proof":
            errors.append("proof_status")
        if _mot_text(row.get("row_id", "")) == "":
            errors.append("row_id")
        if _mot_text(row.get("seller_sku", "")) == "" and _mot_text(row.get("asin", "")) == "":
            errors.append("sku_or_asin")
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            errors.append("source_class")
        if stock_state not in allowed_stock_states:
            errors.append("supplier_stock_state")
        if stock_qty_text:
            try:
                stock_qty = float(stock_qty_text)
            except ValueError:
                stock_qty = -1.0
            if stock_qty < 0 or not stock_qty.is_integer():
                errors.append("supplier_stock_qty")
            if stock_state == "supplier_stock_not_verified":
                errors.append("stock_qty_not_allowed")
            if stock_state == "supplier_stock_verified_zero" and stock_qty != 0:
                errors.append("verified_zero_qty")
            if stock_state == "supplier_stock_verified_in_stock" and stock_qty == 0:
                errors.append("verified_in_stock_zero_qty")
        if backorder_state not in allowed_backorder_states:
            errors.append("backorder_state")
        if backorder_eta:
            if parse_utc(backorder_eta) is None:
                errors.append("backorder_eta")
            if backorder_state != "backorder_wait":
                errors.append("backorder_eta_without_wait")
        if supplier_file_asof and parse_utc(supplier_file_asof) is None:
            errors.append("supplier_file_asof")
        if errors:
            bad_proof_event_rows.append(f"{proof_label}:{'|'.join(errors)}")
    for row in pack_moq_event_rows:
        proof_label = _mot_text(row.get("proof_id", "")) or _mot_text(row.get("row_id", "")) or "missing_pack_moq_proof"
        pack_state = _mot_text(row.get("pack_moq_proof_state", ""))
        pack_multiple = _mot_text(row.get("pack_multiple", ""))
        supplier_moq = _mot_text(row.get("supplier_moq", ""))
        valid_order_step = _mot_text(row.get("valid_order_step", ""))
        proof_status = _mot_text(row.get("proof_status", ""))
        errors: list[str] = []
        if _mot_text(row.get("creates_live_action", "")) != "0":
            errors.append("creates_live_action")
        if proof_status != "draft_proof":
            errors.append("proof_status")
        if _mot_text(row.get("row_id", "")) == "":
            errors.append("row_id")
        if _mot_text(row.get("seller_sku", "")) == "" and _mot_text(row.get("asin", "")) == "":
            errors.append("sku_or_asin")
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            errors.append("source_class")
        if pack_state not in allowed_pack_moq_states:
            errors.append("pack_moq_proof_state")
        for field_name, field_value in (
            ("pack_multiple", pack_multiple),
            ("supplier_moq", supplier_moq),
            ("valid_order_step", valid_order_step),
        ):
            if field_value:
                try:
                    number = float(field_value)
                except ValueError:
                    number = 0.0
                if number <= 0 or not number.is_integer():
                    errors.append(field_name)
        if pack_state == "pack_moq_verified" and valid_order_step == "":
            errors.append("valid_order_step_required")
        if pack_state == "pack_moq_not_verified" and (pack_multiple or supplier_moq or valid_order_step):
            errors.append("pack_fields_not_allowed")
        if errors:
            bad_pack_moq_event_rows.append(f"{proof_label}:{'|'.join(errors)}")
    for row in lines_rows:
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or "missing_row"
        source_class = _mot_text(row.get("source_class", ""))
        if source_class not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        try:
            qty = float(_mot_text(row.get("draft_order_qty", "")))
        except ValueError:
            qty = 0.0
        if qty <= 0 or not qty.is_integer():
            bad_qty_rows.append(row_label)
        if _mot_text(row.get("creates_live_action", "")) != "0":
            live_action_rows.append(row_label)
        state_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("line_state", "action_safety_state")
        )
        if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon")):
            live_language_rows.append(row_label)
        checklist_status = _mot_text(row.get("supplier_proof_checklist_status", ""))
        missing_reasons = supplier_missing_reasons(row)
        visible_missing_reasons = _mot_text(row.get("supplier_proof_missing_reasons", ""))
        if checklist_status == "supplier_proof_clear" and (missing_reasons or visible_missing_reasons):
            bad_supplier_clear_rows.append(row_label)
        elif checklist_status == "needs_supplier_proof" and not visible_missing_reasons:
            missing_supplier_reason_rows.append(row_label)
        elif checklist_status not in {"supplier_proof_clear", "needs_supplier_proof"}:
            missing_supplier_reason_rows.append(row_label)
        readiness_state = _mot_text(row.get("supplier_batch_readiness_state", ""))
        readiness_reasons = _mot_text(row.get("supplier_batch_readiness_reasons", ""))
        line_state = _mot_text(row.get("line_state", ""))
        if readiness_state not in allowed_readiness_states:
            bad_readiness_rows.append(f"{row_label}:unknown_state")
        elif readiness_state == "ready_for_purchase_approval_review_only" and (
            checklist_status != "supplier_proof_clear"
            or line_state != "review_only_ready"
            or _mot_text(row.get("creates_live_action", "")) != "0"
        ):
            bad_readiness_rows.append(row_label)
        elif readiness_state == "blocked_from_purchase_approval" and not readiness_reasons:
            missing_readiness_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        batch_id = _mot_text(row.get("batch_id", "")) or "missing_batch"
        if _mot_text(row.get("creates_live_action", "")) != "0":
            bad_summary_rows.append(f"{batch_id}:creates_live_action")
        state_text = _mot_text(row.get("batch_state", "")).lower()
        if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon")):
            bad_summary_rows.append(f"{batch_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    batch_count = len({_mot_text(row.get("batch_id", "")) for row in summary_rows if _mot_text(row.get("batch_id", ""))})

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O supplier batch draft proof files are missing."
        manager_action = "Run the bounded O464 local supplier batch draft builder. Do not create POs, write Sheets, edit queues, change prices, or run market proof."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more supplier batch draft lines do not have an approved source class."
        manager_action = "Repair source labelling in the O batch draft builder."
    elif bad_qty_rows:
        status = "fail"
        value = f"bad_qty_rows={len(bad_qty_rows)}"
        root_cause = "One or more supplier batch draft lines has an invalid draft quantity."
        manager_action = "Repair draft quantity validation before using supplier batch drafts."
    elif live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = f"live_action_rows={len(live_action_rows)};bad_summary_rows={len(bad_summary_rows)};live_language_rows={len(live_language_rows)}"
        root_cause = "A supplier batch draft looks like a live action or purchase commitment."
        manager_action = "Keep supplier batch drafts review-only and disconnected from purchase orders."
    elif bad_supplier_clear_rows or missing_supplier_reason_rows:
        status = "fail"
        value = f"bad_supplier_clear_rows={len(bad_supplier_clear_rows)};missing_supplier_reason_rows={len(missing_supplier_reason_rows)}"
        root_cause = "A supplier batch draft supplier-proof checklist is unsafe or incomplete."
        manager_action = "Repair checklist proof wording before using supplier batch drafts."
    elif bad_proof_event_rows:
        status = "fail"
        value = f"bad_proof_event_rows={len(bad_proof_event_rows)}"
        root_cause = "A supplier proof event is unsafe or malformed."
        manager_action = "Repair supplier proof capture validation before using supplier batch drafts."
    elif bad_pack_moq_event_rows:
        status = "fail"
        value = f"bad_pack_moq_event_rows={len(bad_pack_moq_event_rows)}"
        root_cause = "A pack/MOQ proof event is unsafe or malformed."
        manager_action = "Repair pack/MOQ proof capture validation before using supplier batch drafts."
    elif bad_readiness_rows or missing_readiness_reason_rows:
        status = "fail"
        value = f"bad_readiness_rows={len(bad_readiness_rows)};missing_readiness_reason_rows={len(missing_readiness_reason_rows)}"
        root_cause = "A supplier batch readiness label is unsafe or incomplete."
        manager_action = "Repair batch readiness logic before using supplier batch drafts."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The O supplier batch draft health file contains a non-ok check."
        manager_action = "Repair the O batch draft proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(lines_rows)};batches={batch_count};summary={len(summary_rows)}"
        root_cause = ""
        manager_action = "No action; supplier batch drafts are local, review-only, and cannot create live buying actions."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_restock_supplier_batch_drafts",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O464_build_restock_supplier_batch_drafts.py",
            expected_output="O supplier batch draft lines, supplier summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(lines_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"proof_events_exists={1 if proof_events_path.exists() else 0};proof_event_rows={len(proof_event_rows)};"
                f"pack_moq_events_exists={1 if pack_moq_events_path.exists() else 0};pack_moq_event_rows={len(pack_moq_event_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"bad_qty_rows={','.join(bad_qty_rows)};live_action_rows={','.join(live_action_rows)};"
                f"bad_summary_rows={','.join(bad_summary_rows)};live_language_rows={','.join(live_language_rows)};"
                f"bad_supplier_clear_rows={','.join(bad_supplier_clear_rows)};"
                f"missing_supplier_reason_rows={','.join(missing_supplier_reason_rows)};"
                f"bad_proof_event_rows={','.join(bad_proof_event_rows)};"
                f"bad_pack_moq_event_rows={','.join(bad_pack_moq_event_rows)};"
                f"bad_readiness_rows={','.join(bad_readiness_rows)};"
                f"missing_readiness_reason_rows={','.join(missing_readiness_reason_rows)};"
                f"health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(lines_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O supplier batch drafts show possible supplier baskets without creating purchase orders.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O supplier batch draft proof only; no purchase commitment, PO creation, receiving, send-to-Amazon, "
                "Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_supplier_file_presence_probe_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_health.csv"
    probe_rows = read_csv_rows(probe_path)
    health_rows = read_csv_rows(health_path)
    paths = [probe_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_states = {
        "exact_supplier_sku_or_barcode_found",
        "not_found_in_latest_local_supplier_file",
        "not_checked_no_supplier_identity",
        "not_checked_no_local_supplier_file",
        "not_checked_supplier_file_read_error",
    }
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )

    unsafe_rows: list[str] = []
    unknown_state_rows: list[str] = []
    bad_match_claim_rows: list[str] = []
    missing_explanation_rows: list[str] = []
    for idx, row in enumerate(probe_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            unsafe_rows.append(row_label)
        match_state = _mot_text(row.get("identity_match_state", ""))
        if match_state not in allowed_states:
            unknown_state_rows.append(row_label)
        if match_state == "exact_supplier_sku_or_barcode_found" and (_o_num(row.get("matched_row_count", "")) or 0) <= 0:
            bad_match_claim_rows.append(row_label)
        if _mot_text(row.get("probe_explanation", "")) == "":
            missing_explanation_rows.append(row_label)

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    found_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", ""))
        for row in probe_rows
        if _mot_text(row.get("identity_match_state", "")) == "exact_supplier_sku_or_barcode_found"
    ]
    not_found_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", ""))
        for row in probe_rows
        if _mot_text(row.get("identity_match_state", "")) == "not_found_in_latest_local_supplier_file"
    ]
    not_checked_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", ""))
        for row in probe_rows
        if _mot_text(row.get("identity_match_state", "")) in {
            "not_checked_no_supplier_identity",
            "not_checked_no_local_supplier_file",
            "not_checked_supplier_file_read_error",
        }
    ]

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O supplier-file presence probe files are missing."
        manager_action = "Run the bounded O492 local supplier-file presence probe. Do not fetch supplier files, edit queues, or clear supplier proof."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file probe row looks like it can clear proof, approve buying, create a PO, or create a live action."
        manager_action = "Repair the O492 local-only flags before using the supplier-file probe."
    elif unknown_state_rows or bad_match_claim_rows or missing_explanation_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"bad_match_claim_rows={len(bad_match_claim_rows)};"
            f"missing_explanation_rows={len(missing_explanation_rows)}"
        )
        root_cause = "A supplier-file probe state is unsafe or unclear."
        manager_action = "Repair the O492 proof wording and match-claim logic before using the probe."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The supplier-file presence probe health file contains a non-ok check."
        manager_action = "Repair the O492 proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"probes={len(probe_rows)};found={len(found_rows)};not_found={len(not_found_rows)};not_checked={len(not_checked_rows)}"
        root_cause = ""
        manager_action = "No action; supplier-file probe is read-only. Missing matches keep rows blocked instead of asking Luke for manual supplier facts."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_file_presence_probe",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O492_build_supplier_file_presence_probe.py",
            expected_output="O supplier-file presence proof shows latest local file match status without clearing supplier proof or approving buying.",
            actual_proof=(
                f"probe_exists={1 if probe_path.exists() else 0};probe_rows={len(probe_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};unsafe_rows={','.join(unsafe_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};"
                f"bad_match_claim_rows={','.join(bad_match_claim_rows)};"
                f"missing_explanation_rows={','.join(missing_explanation_rows)};"
                f"found_rows={','.join(found_rows)};not_found_rows={','.join(not_found_rows)};"
                f"not_checked_rows={','.join(not_checked_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(probe_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O checks latest local supplier files for drafted rows and keeps the result as proof-only context.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O supplier-file presence proof only; no supplier download, supplier file move/delete/rewrite, F061 run, "
                "purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, price change, queue edit, "
                "local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_supplier_file_evidence_visibility_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    review_rows = read_csv_rows(review_path)
    probe_rows = read_csv_rows(probe_path)
    paths = [review_path, probe_path]
    missing = [path.name for path in paths if not path.exists()]
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )
    unsafe_rows: list[str] = []
    file_checked_rows: list[str] = []
    exact_rows: list[str] = []
    not_found_rows: list[str] = []
    no_file_rows: list[str] = []
    read_error_rows: list[str] = []
    file_names: list[str] = []
    for idx, row in enumerate(probe_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        if any(_o_truthy(row.get(column, "")) for column in zero_flag_columns):
            unsafe_rows.append(row_label)
        file_name = _mot_text(row.get("latest_supplier_file_name", ""))
        file_state = _mot_text(row.get("latest_supplier_file_state", "")).lower()
        identity_state = _mot_text(row.get("identity_match_state", ""))
        if file_name or "checked" in file_state:
            file_checked_rows.append(row_label)
        if file_name and file_name not in file_names:
            file_names.append(file_name)
        if identity_state == "exact_supplier_sku_or_barcode_found":
            exact_rows.append(row_label)
        elif identity_state == "not_found_in_latest_local_supplier_file":
            not_found_rows.append(row_label)
        elif identity_state == "not_checked_no_local_supplier_file":
            no_file_rows.append(row_label)
        elif identity_state == "not_checked_supplier_file_read_error" or _mot_text(row.get("read_error", "")):
            read_error_rows.append(row_label)

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier-file evidence visibility panel is missing review or probe source proof."
        manager_action = "Rebuild the local O restock session and supplier-file probe before using the main supplier-file evidence panel."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file evidence row appears to clear proof, approve buying, create a PO, commit buying, or create a live action."
        manager_action = "Keep supplier-file evidence read-only and repair the unsafe flag before using the panel."
    else:
        status = "ok"
        value = (
            f"review_rows={len(review_rows)};probe_rows={len(probe_rows)};files_checked={len(file_checked_rows)};"
            f"exact={len(exact_rows)};not_found={len(not_found_rows)};no_file={len(no_file_rows)};read_error={len(read_error_rows)}"
        )
        root_cause = ""
        manager_action = "Use supplier-file evidence as read-only context only. It does not import files, clear supplier proof, approve buying, or create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_file_evidence_visibility",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O UI supplier-file evidence panel / O492 proof",
            expected_output="The main Restock Session page can show supplier-file evidence without importing files, clearing proof, or enabling buying.",
            actual_proof=(
                f"review_exists={1 if review_path.exists() else 0};review_rows={len(review_rows)};"
                f"probe_exists={1 if probe_path.exists() else 0};probe_rows={len(probe_rows)};"
                f"files_checked={len(file_checked_rows)};exact={len(exact_rows)};not_found={len(not_found_rows)};"
                f"no_file={len(no_file_rows)};read_error={len(read_error_rows)};"
                f"file_examples={','.join(file_names[:3])};unsafe_rows={','.join(unsafe_rows)};missing={','.join(missing)}"
            ),
            row_count=str(len(probe_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O can show local supplier-file evidence in the main restocking view while keeping supplier proof local and manual.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier-file evidence visibility only; no supplier download, supplier file move/delete/rewrite/import, "
                "F061 run, F source-status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_supplier_file_proof_coverage_map_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    review_rows = read_csv_rows(review_path)
    probe_rows = read_csv_rows(probe_path)
    paths = [review_path, probe_path]
    missing = [path.name for path in paths if not path.exists()]
    probe_row_ids = {_mot_text(row.get("row_id", "")) for row in probe_rows if _mot_text(row.get("row_id", ""))}
    probe_skus = {_mot_text(row.get("seller_sku", "")) for row in probe_rows if _mot_text(row.get("seller_sku", ""))}
    covered_rows: list[str] = []
    uncovered_rows: list[str] = []
    all_suppliers: set[str] = set()
    covered_suppliers: set[str] = set()
    uncovered_supplier_counts: dict[str, int] = {}
    for idx, row in enumerate(review_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"review_{idx}"
        supplier = _mot_text(row.get("supplier_name", "")) or _mot_text(row.get("supplier_code", "")) or "(Unknown supplier)"
        all_suppliers.add(supplier)
        row_id = _mot_text(row.get("row_id", ""))
        sku = _mot_text(row.get("seller_sku", ""))
        covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
        if covered:
            covered_rows.append(row_label)
            covered_suppliers.add(supplier)
        else:
            uncovered_rows.append(row_label)
            uncovered_supplier_counts[supplier] = uncovered_supplier_counts.get(supplier, 0) + 1

    review_row_ids = {_mot_text(row.get("row_id", "")) for row in review_rows if _mot_text(row.get("row_id", ""))}
    review_skus = {_mot_text(row.get("seller_sku", "")) for row in review_rows if _mot_text(row.get("seller_sku", ""))}
    matched_probe_rows = [
        row for row in probe_rows
        if (_mot_text(row.get("row_id", "")) in review_row_ids and _mot_text(row.get("row_id", "")) != "")
        or (_mot_text(row.get("seller_sku", "")) in review_skus and _mot_text(row.get("seller_sku", "")) != "")
    ]
    exact_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", ""))
        for row in matched_probe_rows
        if _mot_text(row.get("identity_match_state", "")) == "exact_supplier_sku_or_barcode_found"
    ]
    not_found_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", ""))
        for row in matched_probe_rows
        if _mot_text(row.get("identity_match_state", "")) == "not_found_in_latest_local_supplier_file"
    ]
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )
    unsafe_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        for idx, row in enumerate(matched_probe_rows, start=1)
        if any(_o_truthy(row.get(column, "")) for column in zero_flag_columns)
    ]
    top_uncovered = sorted(uncovered_supplier_counts.items(), key=lambda item: (-item[1], item[0]))[:3]

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier-file proof coverage map is missing review or probe source proof."
        manager_action = "Rebuild the local O restock session and supplier-file probe before using the coverage map."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file probe row appears to clear proof, approve buying, create a PO, commit buying, or create a live action."
        manager_action = "Keep supplier-file proof coverage read-only and repair the unsafe probe flag."
    else:
        status = "ok"
        value = (
            f"review_rows={len(review_rows)};covered={len(covered_rows)};uncovered={len(uncovered_rows)};"
            f"suppliers={len(all_suppliers)};covered_suppliers={len(covered_suppliers)};"
            f"exact={len(exact_rows)};not_found={len(not_found_rows)}"
        )
        root_cause = ""
        manager_action = "Use this as a read-only coverage map. Uncovered rows are a work queue, not a failure, and do not clear supplier proof."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_file_proof_coverage_map",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O UI supplier-file proof coverage map / O492 proof",
            expected_output="A read-only coverage map shows probe-covered and uncovered restock rows without fetching files, clearing proof, or enabling buying.",
            actual_proof=(
                f"review_exists={1 if review_path.exists() else 0};review_rows={len(review_rows)};"
                f"probe_exists={1 if probe_path.exists() else 0};probe_rows={len(probe_rows)};"
                f"covered={len(covered_rows)};uncovered={len(uncovered_rows)};"
                f"suppliers={len(all_suppliers)};covered_suppliers={len(covered_suppliers)};"
                f"exact={len(exact_rows)};not_found={len(not_found_rows)};"
                f"top_uncovered={';'.join(f'{supplier}:{count}' for supplier, count in top_uncovered)};"
                f"unsafe_rows={','.join(unsafe_rows)};missing={','.join(missing)}"
            ),
            row_count=str(len(review_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O can see supplier-file probe coverage gaps before asking Luke to work supplier proof by hand.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier-file proof coverage only; no supplier download, supplier file move/delete/rewrite/import, "
                "F061 run, F source-status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_supplier_proof_work_queue_action(row: dict[str, str]) -> str:
    text = "|".join(
        _mot_text(row.get(field, "")).lower()
        for field in (
            "action_block_reason",
            "missing_input_reasons",
            "supplier_proof_missing_reasons",
            "supplier_batch_readiness_reasons",
            "profit_check_message",
        )
    )
    if "missing_from_latest_supplier_file" in text or "discontinued" in text:
        return "check_later_or_mark_drop"
    if (
        "supplier:" in text
        or "supplier_stock" in text
        or "supplier_cost" in text
        or "missing_supplier_cost" in text
        or _mot_text(row.get("supplier_stock_state", "")).lower() in {"", "supplier_stock_not_verified", "not_verified"}
        or _mot_text(row.get("supplier_match_state", "")).lower() in {"", "not_verified", "supplier_match_not_verified"}
        or _mot_text(row.get("supplier_cost_proof_state", "")).lower() in {"", "missing_supplier_cost", "supplier_cost_not_exact", "bridge_cost_only", "not_verified"}
    ):
        return "supplier_proof"
    if "pack" in text or "moq" in text:
        return "pack_moq_proof"
    if "order:" in text or _mot_text(row.get("order_qty_draft", "")) in {"", "0", "0.0"}:
        return "local_qty"
    return "check_later"


def _o_supplier_proof_work_queue_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    review_rows = read_csv_rows(review_path)
    probe_rows = read_csv_rows(probe_path)
    paths = [review_path, probe_path]
    missing = [path.name for path in paths if not path.exists()]
    probe_row_ids = {_mot_text(row.get("row_id", "")) for row in probe_rows if _mot_text(row.get("row_id", ""))}
    probe_skus = {_mot_text(row.get("seller_sku", "")) for row in probe_rows if _mot_text(row.get("seller_sku", ""))}
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )
    unsafe_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        for idx, row in enumerate(probe_rows, start=1)
        if any(_o_truthy(row.get(column, "")) for column in zero_flag_columns)
    ]
    supplier_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    top_supplier_action_counts: dict[str, int] = {}
    uncovered_count = 0
    for row in review_rows:
        row_id = _mot_text(row.get("row_id", ""))
        sku = _mot_text(row.get("seller_sku", ""))
        covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
        if covered:
            continue
        uncovered_count += 1
        supplier = _mot_text(row.get("supplier_name", "")) or _mot_text(row.get("supplier_code", "")) or "(Unknown supplier)"
        action = _o_supplier_proof_work_queue_action(row)
        supplier_counts[supplier] = supplier_counts.get(supplier, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1

    top_supplier = ""
    top_supplier_rows = 0
    if supplier_counts:
        top_supplier, top_supplier_rows = sorted(supplier_counts.items(), key=lambda item: (-item[1], item[0]))[0]
        for row in review_rows:
            row_id = _mot_text(row.get("row_id", ""))
            sku = _mot_text(row.get("seller_sku", ""))
            covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
            supplier = _mot_text(row.get("supplier_name", "")) or _mot_text(row.get("supplier_code", "")) or "(Unknown supplier)"
            if covered or supplier != top_supplier:
                continue
            action = _o_supplier_proof_work_queue_action(row)
            top_supplier_action_counts[action] = top_supplier_action_counts.get(action, 0) + 1
    top_action = ""
    top_action_rows = 0
    if action_counts:
        top_action, top_action_rows = sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))[0]
    top_supplier_action = ""
    if top_supplier_action_counts:
        top_supplier_action = sorted(top_supplier_action_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    top_supplier_examples = sorted(supplier_counts.items(), key=lambda item: (-item[1], item[0]))[:4]

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier proof work queue is missing review or probe source proof."
        manager_action = "Rebuild the local O restock session and supplier-file probe before using the supplier proof work queue."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file probe row appears to clear proof, approve buying, create a PO, commit buying, or create a live action."
        manager_action = "Keep the supplier proof queue read-only and repair the unsafe probe flag."
    else:
        status = "ok"
        value = (
            f"uncovered={uncovered_count};supplier_groups={len(supplier_counts)};"
            f"top_supplier={top_supplier};top_supplier_rows={top_supplier_rows};"
            f"top_action={top_action};top_action_rows={top_action_rows}"
        )
        root_cause = ""
        manager_action = "Use this as a read-only supplier proof work queue. It does not fetch files or clear proof."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_proof_work_queue",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O UI supplier proof work queue / O492 coverage proof",
            expected_output="A read-only queue groups uncovered supplier-proof rows by supplier and local action without fetching files or clearing proof.",
            actual_proof=(
                f"review_rows={len(review_rows)};probe_rows={len(probe_rows)};uncovered={uncovered_count};"
                f"supplier_groups={len(supplier_counts)};top_supplier={top_supplier};top_supplier_rows={top_supplier_rows};"
                f"top_supplier_action={top_supplier_action};top_action={top_action};top_action_rows={top_action_rows};"
                f"top_supplier_examples={';'.join(f'{supplier}:{count}' for supplier, count in top_supplier_examples)};"
                f"action_counts={';'.join(f'{action}:{count}' for action, count in sorted(action_counts.items()))};"
                f"unsafe_rows={','.join(unsafe_rows)};missing={','.join(missing)}"
            ),
            row_count=str(uncovered_count),
            source_path=";".join(str(path) for path in paths),
            summary="O can now point to the next supplier proof work without turning that queue into a supplier-file or buying action.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier proof work queue only; no supplier download, supplier file move/delete/rewrite/import, "
                "F061 run, F source-status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, proof-event write, or output deletion."
            ),
        )
    ]


def _o_supplier_proof_queue_filter_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    review_rows = read_csv_rows(review_path)
    probe_rows = read_csv_rows(probe_path)
    paths = [review_path, probe_path]
    missing = [path.name for path in paths if not path.exists()]
    probe_row_ids = {_mot_text(row.get("row_id", "")) for row in probe_rows if _mot_text(row.get("row_id", ""))}
    probe_skus = {_mot_text(row.get("seller_sku", "")) for row in probe_rows if _mot_text(row.get("seller_sku", ""))}
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )
    unsafe_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        for idx, row in enumerate(probe_rows, start=1)
        if any(_o_truthy(row.get(column, "")) for column in zero_flag_columns)
    ]
    supplier_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    top_supplier_action_counts: dict[str, int] = {}
    uncovered_count = 0
    for row in review_rows:
        row_id = _mot_text(row.get("row_id", ""))
        sku = _mot_text(row.get("seller_sku", ""))
        covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
        if covered:
            continue
        uncovered_count += 1
        supplier = _mot_text(row.get("supplier_name", "")) or _mot_text(row.get("supplier_code", "")) or "(Unknown supplier)"
        action = _o_supplier_proof_work_queue_action(row)
        supplier_counts[supplier] = supplier_counts.get(supplier, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1

    top_supplier = ""
    top_supplier_rows = 0
    if supplier_counts:
        top_supplier, top_supplier_rows = sorted(supplier_counts.items(), key=lambda item: (-item[1], item[0]))[0]
        for row in review_rows:
            row_id = _mot_text(row.get("row_id", ""))
            sku = _mot_text(row.get("seller_sku", ""))
            covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
            supplier = _mot_text(row.get("supplier_name", "")) or _mot_text(row.get("supplier_code", "")) or "(Unknown supplier)"
            if covered or supplier != top_supplier:
                continue
            action = _o_supplier_proof_work_queue_action(row)
            top_supplier_action_counts[action] = top_supplier_action_counts.get(action, 0) + 1
    top_action = ""
    top_action_rows = 0
    if action_counts:
        top_action, top_action_rows = sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))[0]
    top_supplier_action = ""
    top_supplier_action_rows = 0
    if top_supplier_action_counts:
        top_supplier_action, top_supplier_action_rows = sorted(top_supplier_action_counts.items(), key=lambda item: (-item[1], item[0]))[0]
    option_count = 1
    if uncovered_count:
        option_count += 1
    if top_supplier:
        option_count += 1
    if top_action:
        option_count += 1
    if top_supplier and top_supplier_action:
        option_count += 1

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier proof queue filter is missing review or probe source proof."
        manager_action = "Rebuild the local O restock session and supplier-file probe before using the queue focus filter."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file probe row appears to clear proof, approve buying, create a PO, commit buying, or create a live action."
        manager_action = "Keep the queue focus filter read-only and repair the unsafe probe flag."
    elif uncovered_count > 0 and option_count < 4:
        status = "fail"
        value = f"missing_focus_options={option_count}"
        root_cause = "Supplier proof queue work exists, but the manager cannot derive the expected top supplier/action focus options."
        manager_action = "Repair the queue focus option builder before using the UI filter."
    else:
        status = "ok"
        value = (
            f"options={option_count};uncovered={uncovered_count};top_supplier={top_supplier};"
            f"top_supplier_rows={top_supplier_rows};top_action={top_action};top_action_rows={top_action_rows};"
            f"top_supplier_action={top_supplier_action};top_supplier_action_rows={top_supplier_action_rows}"
        )
        root_cause = ""
        manager_action = "Use this as a read-only queue focus filter. It changes the view only and does not fetch files or clear proof."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_proof_queue_filter",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O UI supplier proof queue focus filter / O492 coverage proof",
            expected_output="A read-only filter can focus current supplier, all uncovered rows, top supplier, top action, or top supplier plus action.",
            actual_proof=(
                f"review_rows={len(review_rows)};probe_rows={len(probe_rows)};uncovered={uncovered_count};"
                f"option_count={option_count};top_supplier={top_supplier};top_supplier_rows={top_supplier_rows};"
                f"top_action={top_action};top_action_rows={top_action_rows};"
                f"top_supplier_action={top_supplier_action};top_supplier_action_rows={top_supplier_action_rows};"
                f"unsafe_rows={','.join(unsafe_rows)};missing={','.join(missing)}"
            ),
            row_count=str(uncovered_count),
            source_path=";".join(str(path) for path in paths),
            summary="O can focus the supplier proof queue without turning that focus into a supplier-file or buying action.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier proof queue focus only; no supplier download, supplier file move/delete/rewrite/import, "
                "F061 run, F source-status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, proof-event write, or output deletion."
            ),
        )
    ]


def _o_supplier_proof_action_field_flags(row: dict[str, str]) -> dict[str, bool]:
    text = "|".join(
        _mot_text(row.get(field, "")).lower()
        for field in (
            "action_block_reason",
            "missing_input_reasons",
            "supplier_proof_missing_reasons",
            "supplier_batch_readiness_reasons",
            "profit_check_message",
            "operator_decision_state",
            "supplier_file_card_state",
            "supplier_file_card_detail",
        )
    )
    supplier_match_state = _mot_text(row.get("supplier_match_state", "")).lower()
    supplier_proof_state = _mot_text(row.get("supplier_proof_state", "")).lower()
    supplier_file_state = _mot_text(row.get("supplier_file_card_state", "")).lower()
    supplier_stock_state = _mot_text(row.get("supplier_stock_state", "")).lower()
    backorder_state = _mot_text(row.get("backorder_state", "")).lower()
    supplier_cost_state = _mot_text(row.get("supplier_cost_proof_state", "")).lower()
    current_supplier_cost = _mot_text(row.get("current_supplier_cost_gbp", "")) or _mot_text(row.get("supplier_cost_gbp", "")) or _mot_text(row.get("buy_cost_gbp", ""))
    supplier_file_asof = _mot_text(row.get("supplier_file_asof_utc", "")) or _mot_text(row.get("supplier_file_card_file_mtime_utc", ""))
    supplier_file_ref = _mot_text(row.get("supplier_file_reference", "")) or _mot_text(row.get("supplier_file_card_file_name", "")) or _mot_text(row.get("latest_supplier_file_name", ""))
    action = _o_supplier_proof_work_queue_action(row)
    return {
        "exact_match": (
            "missing_supplier_match" in text
            or "exact_supplier_match_not_proved" in text
            or "supplier_match" in text
            or supplier_match_state in {"", "not_verified", "supplier_match_not_verified"}
            or supplier_proof_state in {"", "not_verified", "supplier_proof_missing", "exact_supplier_match_not_proved"}
            or supplier_file_state in {"not_found_in_latest_local_supplier_file", "not_checked_no_supplier_identity"}
        ),
        "stock_backorder": (
            "supplier_stock" in text
            or "backorder" in text
            or supplier_stock_state in {"", "supplier_stock_not_verified", "not_verified"}
            or backorder_state in {"", "backorder_not_verified", "not_verified"}
        ),
        "cost": (
            "supplier_cost" in text
            or "missing_supplier_cost" in text
            or supplier_cost_state in {"", "missing_supplier_cost", "supplier_cost_not_exact", "bridge_cost_only", "not_verified"}
            or current_supplier_cost in {"", "0", "0.0"}
        ),
        "file_ref": (
            "supplier_file_asof_missing" in text
            or "supplier_file" in text
            or supplier_file_state in {"", "not_checked_no_local_supplier_file", "not_checked_supplier_file_read_error", "not_checked_no_supplier_identity"}
            or supplier_file_asof == ""
            or supplier_file_ref == ""
        ),
        "drop_or_check_later": (
            action == "check_later_or_mark_drop"
            or "missing_from_latest_supplier_file" in text
            or "likely_discontinued" in text
            or "discontinued" in text
            or supplier_file_state in {"not_found_in_latest_local_supplier_file", "not_checked_no_local_supplier_file", "not_checked_supplier_file_read_error"}
        ),
    }


def _o_supplier_proof_action_workbench_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    review_rows = read_csv_rows(review_path)
    probe_rows = read_csv_rows(probe_path)
    paths = [review_path, probe_path]
    missing = [path.name for path in paths if not path.exists()]
    probe_row_ids = {_mot_text(row.get("row_id", "")) for row in probe_rows if _mot_text(row.get("row_id", ""))}
    probe_skus = {_mot_text(row.get("seller_sku", "")) for row in probe_rows if _mot_text(row.get("seller_sku", ""))}
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )
    unsafe_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        for idx, row in enumerate(probe_rows, start=1)
        if any(_o_truthy(row.get(column, "")) for column in zero_flag_columns)
    ]
    field_counts = {
        "exact_match": 0,
        "stock_backorder": 0,
        "cost": 0,
        "file_ref": 0,
        "drop_or_check_later": 0,
    }
    uncovered_count = 0
    for row in review_rows:
        row_id = _mot_text(row.get("row_id", ""))
        sku = _mot_text(row.get("seller_sku", ""))
        covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
        if covered:
            continue
        uncovered_count += 1
        flags = _o_supplier_proof_action_field_flags(row)
        for field, flagged in flags.items():
            if flagged:
                field_counts[field] = field_counts.get(field, 0) + 1

    top_field = ""
    top_field_rows = 0
    active_fields = [(field, count) for field, count in field_counts.items() if count > 0]
    if active_fields:
        top_field, top_field_rows = sorted(active_fields, key=lambda item: (-item[1], item[0]))[0]

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier proof action workbench is missing review or probe source proof."
        manager_action = "Rebuild the local O restock session and supplier-file probe before using the action workbench."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file probe row appears to clear proof, approve buying, create a PO, commit buying, or create a live action."
        manager_action = "Keep the supplier proof action workbench read-only and repair the unsafe probe flag."
    else:
        status = "ok"
        value = (
            f"rows={uncovered_count};exact_match={field_counts['exact_match']};"
            f"stock_backorder={field_counts['stock_backorder']};cost={field_counts['cost']};"
            f"file_ref={field_counts['file_ref']};drop_or_check_later={field_counts['drop_or_check_later']};"
            f"top_field={top_field};top_field_rows={top_field_rows}"
        )
        root_cause = ""
        manager_action = "Use this as a read-only proof-field checklist. Missing fields are construction work, not a buying approval."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_proof_action_workbench",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O UI supplier proof action workbench / O492 coverage proof",
            expected_output="A read-only workbench counts which supplier proof fields need checking without fetching files, clearing proof, or enabling buying.",
            actual_proof=(
                f"review_rows={len(review_rows)};probe_rows={len(probe_rows)};uncovered={uncovered_count};"
                f"exact_match={field_counts['exact_match']};stock_backorder={field_counts['stock_backorder']};"
                f"cost={field_counts['cost']};file_ref={field_counts['file_ref']};"
                f"drop_or_check_later={field_counts['drop_or_check_later']};top_field={top_field};"
                f"top_field_rows={top_field_rows};unsafe_rows={','.join(unsafe_rows)};missing={','.join(missing)}"
            ),
            row_count=str(uncovered_count),
            source_path=";".join(str(path) for path in paths),
            summary="O can show which supplier proof fields to work next without turning proof review into a purchase path.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier proof action workbench only; no supplier download, supplier file move/delete/rewrite/import, "
                "F061 run, F source-status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, proof-event write, or output deletion."
            ),
        )
    ]


def _o_supplier_proof_field_focus_filter_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    probe_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_presence_probe_live.csv"
    review_rows = read_csv_rows(review_path)
    probe_rows = read_csv_rows(probe_path)
    paths = [review_path, probe_path]
    missing = [path.name for path in paths if not path.exists()]
    probe_row_ids = {_mot_text(row.get("row_id", "")) for row in probe_rows if _mot_text(row.get("row_id", ""))}
    probe_skus = {_mot_text(row.get("seller_sku", "")) for row in probe_rows if _mot_text(row.get("seller_sku", ""))}
    zero_flag_columns = (
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
    )
    unsafe_rows = [
        _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"probe_{idx}"
        for idx, row in enumerate(probe_rows, start=1)
        if any(_o_truthy(row.get(column, "")) for column in zero_flag_columns)
    ]
    field_counts = {
        "exact_match": 0,
        "stock_backorder": 0,
        "cost": 0,
        "file_ref": 0,
        "drop_or_check_later": 0,
    }
    uncovered_count = 0
    for row in review_rows:
        row_id = _mot_text(row.get("row_id", ""))
        sku = _mot_text(row.get("seller_sku", ""))
        covered = (row_id in probe_row_ids and row_id != "") or (sku in probe_skus and sku != "")
        if covered:
            continue
        uncovered_count += 1
        flags = _o_supplier_proof_action_field_flags(row)
        for field, flagged in flags.items():
            if flagged:
                field_counts[field] = field_counts.get(field, 0) + 1

    option_count = 1 + sum(1 for count in field_counts.values() if count > 0)
    top_field = ""
    top_field_rows = 0
    active_fields = [(field, count) for field, count in field_counts.items() if count > 0]
    if active_fields:
        top_field, top_field_rows = sorted(active_fields, key=lambda item: (-item[1], item[0]))[0]

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier proof field-focus filter is missing review or probe source proof."
        manager_action = "Rebuild the local O restock session and supplier-file probe before using the field-focus filter."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file probe row appears to clear proof, approve buying, create a PO, commit buying, or create a live action."
        manager_action = "Keep the supplier proof field-focus filter read-only and repair the unsafe probe flag."
    elif uncovered_count > 0 and option_count < 2:
        status = "fail"
        value = f"missing_field_options={option_count}"
        root_cause = "Supplier proof rows exist, but the manager cannot derive field-focus options."
        manager_action = "Repair the field-focus option builder before using the UI filter."
    else:
        status = "ok"
        value = (
            f"options={option_count};rows={uncovered_count};exact_match={field_counts['exact_match']};"
            f"stock_backorder={field_counts['stock_backorder']};cost={field_counts['cost']};"
            f"file_ref={field_counts['file_ref']};drop_or_check_later={field_counts['drop_or_check_later']};"
            f"top_field={top_field};top_field_rows={top_field_rows}"
        )
        root_cause = ""
        manager_action = "Use this as a read-only proof-field filter. It changes the view only and does not save proof or approve buying."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_proof_field_focus_filter",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O UI supplier proof field-focus filter / O492 coverage proof",
            expected_output="A read-only filter can focus supplier-proof queue rows by exact match, stock/backorder, cost, file/ref, or drop/check-later.",
            actual_proof=(
                f"review_rows={len(review_rows)};probe_rows={len(probe_rows)};uncovered={uncovered_count};"
                f"option_count={option_count};exact_match={field_counts['exact_match']};"
                f"stock_backorder={field_counts['stock_backorder']};cost={field_counts['cost']};"
                f"file_ref={field_counts['file_ref']};drop_or_check_later={field_counts['drop_or_check_later']};"
                f"top_field={top_field};top_field_rows={top_field_rows};unsafe_rows={','.join(unsafe_rows)};missing={','.join(missing)}"
            ),
            row_count=str(uncovered_count),
            source_path=";".join(str(path) for path in paths),
            summary="O can focus supplier proof by field type without turning that focus into a supplier-file or buying action.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier proof field-focus filter only; no supplier download, supplier file move/delete/rewrite/import, "
                "F061 run, F source-status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, proof-event write, or output deletion."
            ),
        )
    ]


def _o_supplier_file_source_index_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    index_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_source_index_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_supplier_file_source_index_health.csv"
    index_rows = read_csv_rows(index_path)
    health_rows = read_csv_rows(health_path)
    paths = [index_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_states = {
        "local_file_available_no_f_status",
        "local_file_newer_than_f_status",
        "f_status_failed_local_file_available",
        "f_status_matches_local_file",
        "f_status_ready_but_local_file_missing",
        "no_local_supplier_file",
    }
    zero_flag_columns = (
        "clears_supplier_proof",
        "imports_supplier_file",
        "updates_f_status",
        "creates_live_action",
    )

    unsafe_rows: list[str] = []
    unknown_state_rows: list[str] = []
    missing_explanation_rows: list[str] = []
    for idx, row in enumerate(index_rows, start=1):
        supplier = _mot_text(row.get("supplier_key", "")) or _mot_text(row.get("supplier_name", "")) or f"supplier_{idx}"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            unsafe_rows.append(supplier)
        if _mot_text(row.get("source_handoff_state", "")) not in allowed_states:
            unknown_state_rows.append(supplier)
        if _mot_text(row.get("handoff_explanation", "")) == "":
            missing_explanation_rows.append(supplier)

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    local_file_rows = [
        _mot_text(row.get("supplier_key", "")) or _mot_text(row.get("supplier_name", ""))
        for row in index_rows
        if _mot_text(row.get("local_latest_file_path", "")) != ""
    ]
    failed_f_local_rows = [
        _mot_text(row.get("supplier_key", "")) or _mot_text(row.get("supplier_name", ""))
        for row in index_rows
        if _mot_text(row.get("source_handoff_state", "")) == "f_status_failed_local_file_available"
    ]
    local_newer_rows = [
        _mot_text(row.get("supplier_key", "")) or _mot_text(row.get("supplier_name", ""))
        for row in index_rows
        if _mot_text(row.get("source_handoff_state", "")) == "local_file_newer_than_f_status"
    ]

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O supplier-file source index files are missing."
        manager_action = "Run the bounded O494 local source-index builder. Do not fetch/import files or rewrite F status."
    elif unsafe_rows:
        status = "fail"
        value = f"unsafe_rows={len(unsafe_rows)}"
        root_cause = "A supplier-file source-index row looks like it can import files, rewrite F, clear proof, or create a live action."
        manager_action = "Repair the O494 local-only flags before using the source index."
    elif unknown_state_rows or missing_explanation_rows:
        status = "fail"
        value = f"unknown_state_rows={len(unknown_state_rows)};missing_explanation_rows={len(missing_explanation_rows)}"
        root_cause = "A supplier-file source-index state is unsafe or unclear."
        manager_action = "Repair the O494 state wording before using the source index."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The supplier-file source-index health file contains a non-ok check."
        manager_action = "Repair the O494 proof source instead of masking the UI output."
    else:
        status = "ok"
        value = (
            f"index_rows={len(index_rows)};local_files={len(local_file_rows)};"
            f"f_failed_local_available={len(failed_f_local_rows)};local_newer={len(local_newer_rows)}"
        )
        root_cause = ""
        manager_action = "No action; O can use local source-index proof while keeping F status and buying actions untouched."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_supplier_file_source_index",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O494_build_supplier_file_source_index.py",
            expected_output="O supplier-file source index compares F source status with local supplier folders without importing files or rewriting F.",
            actual_proof=(
                f"index_exists={1 if index_path.exists() else 0};index_rows={len(index_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};unsafe_rows={','.join(unsafe_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};"
                f"missing_explanation_rows={','.join(missing_explanation_rows)};"
                f"local_file_rows={','.join(local_file_rows)};"
                f"failed_f_local_rows={','.join(failed_f_local_rows)};"
                f"local_newer_rows={','.join(local_newer_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(index_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O keeps a read-only supplier-file source index so stale F source proof does not force Luke into manual data entry.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O supplier-file source-index proof only; no supplier download/import, supplier file move/delete/rewrite, "
                "F061 run, F status rewrite, purchase commitment, PO creation, receiving, send-to-Amazon, Sheet write, "
                "price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_purchase_approval_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_preview_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_preview_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_preview_health.csv"
    lines_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    ready_state = "ready_for_purchase_approval_review_only"
    blocked_state = "blocked_from_purchase_approval_review"

    invalid_source_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    unknown_state_rows: list[str] = []
    for row in lines_rows:
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or "missing_row"
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        if _mot_text(row.get("creates_live_action", "")) != "0":
            live_action_rows.append(row_label)
        state_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("approval_preview_state", "supplier_batch_readiness_state")
        )
        if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon", "approved")):
            live_language_rows.append(row_label)
        approval_state = _mot_text(row.get("approval_preview_state", ""))
        if approval_state not in {ready_state, blocked_state}:
            unknown_state_rows.append(row_label)
        elif approval_state == ready_state and (
            _mot_text(row.get("supplier_batch_readiness_state", "")) != "ready_for_purchase_approval_review_only"
            or _mot_text(row.get("supplier_proof_checklist_status", "")) != "supplier_proof_clear"
            or _mot_text(row.get("creates_live_action", "")) != "0"
        ):
            false_ready_rows.append(row_label)
        elif approval_state == blocked_state and _mot_text(row.get("approval_block_reasons", "")) == "":
            missing_block_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        packet_id = _mot_text(row.get("approval_packet_id", "")) or "missing_packet"
        if _mot_text(row.get("creates_live_action", "")) != "0":
            bad_summary_rows.append(f"{packet_id}:creates_live_action")
        state_text = _mot_text(row.get("approval_packet_state", "")).lower()
        if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon", "approved")):
            bad_summary_rows.append(f"{packet_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    packet_count = len({_mot_text(row.get("approval_packet_id", "")) for row in summary_rows if _mot_text(row.get("approval_packet_id", ""))})
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O purchase approval preview proof files are missing."
        manager_action = "Run the bounded O470 local approval preview builder. Do not create POs or capture approvals."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more approval preview lines do not have an approved source class."
        manager_action = "Repair preview source labelling before using the approval preview."
    elif live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = f"live_action_rows={len(live_action_rows)};bad_summary_rows={len(bad_summary_rows)};live_language_rows={len(live_language_rows)}"
        root_cause = "The approval preview looks like a live approval, purchase order, or purchase commitment."
        manager_action = "Keep approval preview review-only and disconnected from purchase orders."
    elif unknown_state_rows or false_ready_rows or missing_block_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_block_reason_rows={len(missing_block_reason_rows)}"
        )
        root_cause = "The approval preview readiness wording is unsafe or incomplete."
        manager_action = "Repair approval preview readiness logic before using the preview."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The approval preview health file contains a non-ok check."
        manager_action = "Repair the approval preview proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(lines_rows)};packets={packet_count};summary={len(summary_rows)}"
        root_cause = ""
        manager_action = "No action; purchase approval preview is local, review-only, and cannot create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_purchase_approval_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O470_build_purchase_approval_preview.py",
            expected_output="O purchase-approval preview lines, supplier packet summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(lines_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"live_action_rows={','.join(live_action_rows)};bad_summary_rows={','.join(bad_summary_rows)};"
                f"live_language_rows={','.join(live_language_rows)};unknown_state_rows={','.join(unknown_state_rows)};"
                f"false_ready_rows={','.join(false_ready_rows)};missing_block_reason_rows={','.join(missing_block_reason_rows)};"
                f"health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(lines_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O purchase approval preview shows review packets without approving buying or creating purchase orders.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O purchase approval preview proof only; no purchase commitment, approval capture, PO creation, receiving, "
                "send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_purchase_approval_guardrail_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    events_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_decision_events.csv"
    guardrails_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_guardrails_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_guardrails_health.csv"
    event_rows = read_csv_rows(events_path)
    guardrail_rows = read_csv_rows(guardrails_path)
    health_rows = read_csv_rows(health_path)
    paths = [events_path, guardrails_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_decision_states = {
        "local_review_accept_not_commitment",
        "local_review_reject",
        "local_review_more_proof_needed",
    }
    allowed_guardrail_states = {
        "local_review_accept_not_commitment",
        "local_review_reject",
        "local_review_more_proof_needed",
        "no_local_review_decision",
        "blocked_preview_not_ready",
        "blocked_local_review_stale",
    }
    ready_preview_state = "ready_for_purchase_approval_review_only"
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approved_for_po",
        "approval_applied",
        "live_action",
    )

    invalid_event_rows: list[str] = []
    live_action_event_rows: list[str] = []
    live_language_event_rows: list[str] = []
    for idx, row in enumerate(event_rows, start=1):
        row_label = _mot_text(row.get("decision_id", "")) or f"event_{idx}"
        if _mot_text(row.get("approval_packet_id", "")) == "":
            invalid_event_rows.append(f"{row_label}:missing_packet")
        if _mot_text(row.get("decision_state", "")) not in allowed_decision_states:
            invalid_event_rows.append(f"{row_label}:decision_state")
        if _mot_text(row.get("decision_status", "")) != "draft_guardrail_decision":
            invalid_event_rows.append(f"{row_label}:decision_status")
        if _mot_text(row.get("creates_live_action", "")) != "0":
            live_action_event_rows.append(row_label)
        event_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("decision_state", "decision_status", "decision_note", "event_source_reference")
        )
        if any(token in event_text for token in unsafe_tokens):
            live_language_event_rows.append(row_label)

    unknown_guardrail_rows: list[str] = []
    live_action_guardrail_rows: list[str] = []
    live_language_guardrail_rows: list[str] = []
    false_accept_rows: list[str] = []
    for idx, row in enumerate(guardrail_rows, start=1):
        packet_id = _mot_text(row.get("approval_packet_id", "")) or f"guardrail_{idx}"
        guardrail_state = _mot_text(row.get("approval_guardrail_state", ""))
        if guardrail_state not in allowed_guardrail_states:
            unknown_guardrail_rows.append(packet_id)
        if _mot_text(row.get("creates_live_action", "")) != "0":
            live_action_guardrail_rows.append(packet_id)
        guardrail_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("approval_guardrail_state", "approval_guardrail_reasons", "latest_decision_state")
        )
        if any(token in guardrail_text for token in unsafe_tokens):
            live_language_guardrail_rows.append(packet_id)
        if guardrail_state == "local_review_accept_not_commitment" and (
            _mot_text(row.get("preview_packet_state", "")) != ready_preview_state
            or _mot_text(row.get("latest_decision_state", "")) != "local_review_accept_not_commitment"
            or _mot_text(row.get("creates_live_action", "")) != "0"
        ):
            false_accept_rows.append(packet_id)

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O approval decision guardrail proof files are missing."
        manager_action = "Run the bounded O472 local approval guardrail builder. Do not create POs."
    elif invalid_event_rows:
        status = "fail"
        value = f"invalid_events={len(invalid_event_rows)}"
        root_cause = "One or more local approval decision events is malformed."
        manager_action = "Repair the local decision event contract before using approval guardrails."
    elif live_action_event_rows or live_action_guardrail_rows or live_language_event_rows or live_language_guardrail_rows:
        status = "fail"
        value = (
            f"live_action_events={len(live_action_event_rows)};"
            f"live_action_guardrails={len(live_action_guardrail_rows)};"
            f"live_language_events={len(live_language_event_rows)};"
            f"live_language_guardrails={len(live_language_guardrail_rows)}"
        )
        root_cause = "The approval guardrail looks like a live approval, purchase order, or purchase commitment."
        manager_action = "Keep approval guardrails local-only and disconnected from purchase orders."
    elif unknown_guardrail_rows or false_accept_rows:
        status = "fail"
        value = f"unknown_guardrails={len(unknown_guardrail_rows)};false_accept_rows={len(false_accept_rows)}"
        root_cause = "The approval guardrail readiness wording is unsafe or incomplete."
        manager_action = "Repair approval guardrail readiness logic before using the local review state."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The approval guardrail health file contains a non-ok check."
        manager_action = "Repair the approval guardrail proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"events={len(event_rows)};guardrails={len(guardrail_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; approval guardrails are local-only and cannot create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_purchase_approval_guardrails",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O472_build_purchase_approval_guardrails.py",
            expected_output="O local approval decision events, current guardrail state, and health proof remain local-only.",
            actual_proof=(
                f"events_exists={1 if events_path.exists() else 0};event_rows={len(event_rows)};"
                f"guardrails_exists={1 if guardrails_path.exists() else 0};guardrail_rows={len(guardrail_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_events={','.join(invalid_event_rows)};"
                f"live_action_events={','.join(live_action_event_rows)};"
                f"live_action_guardrails={','.join(live_action_guardrail_rows)};"
                f"live_language_events={','.join(live_language_event_rows)};"
                f"live_language_guardrails={','.join(live_language_guardrail_rows)};"
                f"unknown_guardrails={','.join(unknown_guardrail_rows)};"
                f"false_accept_rows={','.join(false_accept_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(guardrail_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O approval decision guardrails show local review state without approving buying or creating purchase orders.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O approval decision guardrail proof only; no purchase commitment, PO creation, receiving, send-to-Amazon, "
                "Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_readiness_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_readiness_preview_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_readiness_preview_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_readiness_preview_health.csv"
    line_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    ready_state = "ready_for_local_po_draft_review_only"
    blocked_state = "blocked_from_local_po_draft_review"
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_source_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    for idx, row in enumerate(line_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"line_{idx}"
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        if _mot_text(row.get("creates_live_action", "")) != "0" or _mot_text(row.get("po_creation_allowed", "")) != "0":
            live_action_rows.append(row_label)
        line_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("po_draft_readiness_state", "po_draft_block_reasons")
        )
        if any(token in line_text for token in unsafe_tokens):
            live_language_rows.append(row_label)
        state = _mot_text(row.get("po_draft_readiness_state", ""))
        if state not in {ready_state, blocked_state}:
            unknown_state_rows.append(row_label)
        elif state == ready_state and (
            _mot_text(row.get("approval_preview_state", "")) != "ready_for_purchase_approval_review_only"
            or _mot_text(row.get("approval_guardrail_state", "")) != "local_review_accept_not_commitment"
            or _o_num(row.get("draft_order_qty", "")) is None
            or (_o_num(row.get("draft_order_qty", "")) or 0) <= 0
            or _o_num(row.get("current_supplier_cost_gbp", "")) is None
            or (_o_num(row.get("current_supplier_cost_gbp", "")) or 0) <= 0
            or _mot_text(row.get("supplier_proof_checklist_status", "")) != "supplier_proof_clear"
        ):
            false_ready_rows.append(row_label)
        elif state == blocked_state and _mot_text(row.get("po_draft_block_reasons", "")) == "":
            missing_block_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        packet_id = _mot_text(row.get("approval_packet_id", "")) or "missing_packet"
        if _mot_text(row.get("creates_live_action", "")) != "0" or _mot_text(row.get("po_creation_allowed", "")) != "0":
            bad_summary_rows.append(f"{packet_id}:live_action")
        summary_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("po_draft_preview_state", "po_draft_block_reasons")
        )
        if any(token in summary_text for token in unsafe_tokens):
            bad_summary_rows.append(f"{packet_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft readiness preview files are missing."
        manager_action = "Run the bounded O474 local PO readiness preview builder. Do not create POs."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more PO readiness preview lines do not have an approved source class."
        manager_action = "Repair PO readiness source labelling before using the preview."
    elif live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = (
            f"live_action_rows={len(live_action_rows)};"
            f"bad_summary_rows={len(bad_summary_rows)};"
            f"live_language_rows={len(live_language_rows)}"
        )
        root_cause = "The PO readiness preview looks like a live PO action or purchase commitment."
        manager_action = "Keep PO readiness preview local-only and disconnected from purchase order creation."
    elif unknown_state_rows or false_ready_rows or missing_block_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_block_reason_rows={len(missing_block_reason_rows)}"
        )
        root_cause = "The PO readiness preview readiness wording is unsafe or incomplete."
        manager_action = "Repair PO readiness logic before using the preview."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO readiness preview health file contains a non-ok check."
        manager_action = "Repair the PO readiness proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(line_rows)};summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft readiness preview is local-only and cannot create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_readiness_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O474_build_po_draft_readiness_preview.py",
            expected_output="O local PO draft readiness preview lines, summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(line_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"live_action_rows={','.join(live_action_rows)};bad_summary_rows={','.join(bad_summary_rows)};"
                f"live_language_rows={','.join(live_language_rows)};unknown_state_rows={','.join(unknown_state_rows)};"
                f"false_ready_rows={','.join(false_ready_rows)};missing_block_reason_rows={','.join(missing_block_reason_rows)};"
                f"health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(line_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft readiness preview shows local readiness without creating purchase orders.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft readiness preview proof only; no real PO, no purchase_order file write, no purchase commitment, "
                "receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_line_design_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_po_line_design_preview_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_line_design_preview_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_line_design_preview_health.csv"
    line_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    source_ready_state = "ready_for_local_po_draft_review_only"
    ready_state = "ready_for_local_po_line_design_review_only"
    blocked_state = "blocked_from_local_po_line_design_review"
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_source_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    for idx, row in enumerate(line_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"line_{idx}"
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(row_label)
        line_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("line_design_state", "line_design_block_reasons")
        )
        if any(token in line_text for token in unsafe_tokens):
            live_language_rows.append(row_label)
        state = _mot_text(row.get("line_design_state", ""))
        if state not in {ready_state, blocked_state}:
            unknown_state_rows.append(row_label)
        elif state == ready_state and (
            _mot_text(row.get("source_po_draft_readiness_state", "")) != source_ready_state
            or _o_num(row.get("designed_order_qty", "")) is None
            or (_o_num(row.get("designed_order_qty", "")) or 0) <= 0
            or _o_num(row.get("designed_unit_cost_gbp", "")) is None
            or (_o_num(row.get("designed_unit_cost_gbp", "")) or 0) <= 0
            or _o_num(row.get("designed_line_value_gbp", "")) is None
            or (_o_num(row.get("designed_line_value_gbp", "")) or 0) <= 0
        ):
            false_ready_rows.append(row_label)
        elif state == blocked_state and _mot_text(row.get("line_design_block_reasons", "")) == "":
            missing_block_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        packet_id = _mot_text(row.get("po_line_design_packet_id", "")) or "missing_packet"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            bad_summary_rows.append(f"{packet_id}:action_flag")
        summary_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("line_design_packet_state", "line_design_block_reasons")
        )
        if any(token in summary_text for token in unsafe_tokens):
            bad_summary_rows.append(f"{packet_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO line design preview files are missing."
        manager_action = "Run the bounded O476 local PO line design preview builder. Do not create POs."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more PO line design preview rows do not have an approved source class."
        manager_action = "Repair PO line design source labelling before using the preview."
    elif live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = (
            f"live_action_rows={len(live_action_rows)};"
            f"bad_summary_rows={len(bad_summary_rows)};"
            f"live_language_rows={len(live_language_rows)}"
        )
        root_cause = "The PO line design preview looks like a live PO, buying, receiving, or Amazon action."
        manager_action = "Keep PO line design preview local-only and disconnected from PO files and downstream actions."
    elif unknown_state_rows or false_ready_rows or missing_block_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_block_reason_rows={len(missing_block_reason_rows)}"
        )
        root_cause = "The PO line design preview readiness wording is unsafe or incomplete."
        manager_action = "Repair PO line design logic before using the preview."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO line design preview health file contains a non-ok check."
        manager_action = "Repair the PO line design proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(line_rows)};summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO line design preview is local-only and cannot create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_line_design_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O476_build_po_line_design_preview.py",
            expected_output="O local PO line design preview lines, summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(line_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"live_action_rows={','.join(live_action_rows)};bad_summary_rows={','.join(bad_summary_rows)};"
                f"live_language_rows={','.join(live_language_rows)};unknown_state_rows={','.join(unknown_state_rows)};"
                f"false_ready_rows={','.join(false_ready_rows)};missing_block_reason_rows={','.join(missing_block_reason_rows)};"
                f"health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(line_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO line design preview shows local PO-line shape without writing PO files or creating downstream actions.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO line design preview proof only; no real PO, no purchase order file write, no purchase commitment, "
                "receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_packet_review_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_packet_review_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_packet_review_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_packet_review_health.csv"
    line_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    source_ready_state = "ready_for_local_po_line_design_review_only"
    ready_state = "ready_for_local_po_draft_packet_review_only"
    blocked_state = "blocked_from_local_po_draft_packet_review"
    source_flag_columns = (
        "source_po_file_write_allowed",
        "source_po_creation_allowed",
        "source_purchase_commitment_allowed",
        "source_receiving_allowed",
        "source_send_to_amazon_allowed",
        "source_creates_live_action",
    )
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_source_rows: list[str] = []
    source_action_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    for idx, row in enumerate(line_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"line_{idx}"
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns):
            source_action_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(row_label)
        line_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("packet_review_line_state", "packet_review_block_reasons")
        )
        if any(token in line_text for token in unsafe_tokens):
            live_language_rows.append(row_label)
        state = _mot_text(row.get("packet_review_line_state", ""))
        if state not in {ready_state, blocked_state}:
            unknown_state_rows.append(row_label)
        elif state == ready_state and (
            _mot_text(row.get("po_line_design_packet_id", "")) == ""
            or _mot_text(row.get("source_line_design_state", "")) != source_ready_state
            or any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns)
            or _o_num(row.get("review_order_qty", "")) is None
            or (_o_num(row.get("review_order_qty", "")) or 0) <= 0
            or _o_num(row.get("review_unit_cost_gbp", "")) is None
            or (_o_num(row.get("review_unit_cost_gbp", "")) or 0) <= 0
            or _o_num(row.get("review_line_value_gbp", "")) is None
            or (_o_num(row.get("review_line_value_gbp", "")) or 0) <= 0
        ):
            false_ready_rows.append(row_label)
        elif state == blocked_state and _mot_text(row.get("packet_review_block_reasons", "")) == "":
            missing_block_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        review_id = _mot_text(row.get("po_draft_packet_review_id", "")) or "missing_packet"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            bad_summary_rows.append(f"{review_id}:action_flag")
        summary_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("packet_review_state", "packet_review_block_reasons")
        )
        if any(token in summary_text for token in unsafe_tokens):
            bad_summary_rows.append(f"{review_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft packet review files are missing."
        manager_action = "Run the bounded O478 local PO draft packet review builder. Do not create POs."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more PO draft packet review rows do not have an approved source class."
        manager_action = "Repair PO draft packet source labelling before using the preview."
    elif source_action_rows or live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = (
            f"source_action_rows={len(source_action_rows)};"
            f"live_action_rows={len(live_action_rows)};"
            f"bad_summary_rows={len(bad_summary_rows)};"
            f"live_language_rows={len(live_language_rows)}"
        )
        root_cause = "The PO draft packet review looks like a live PO, buying, receiving, or Amazon action."
        manager_action = "Keep PO draft packet review local-only and disconnected from PO files and downstream actions."
    elif unknown_state_rows or false_ready_rows or missing_block_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_block_reason_rows={len(missing_block_reason_rows)}"
        )
        root_cause = "The PO draft packet review readiness wording is unsafe or incomplete."
        manager_action = "Repair PO draft packet review logic before using the preview."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO draft packet review health file contains a non-ok check."
        manager_action = "Repair the PO draft packet review proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(line_rows)};summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft packet review is local-only and cannot create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_packet_review",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O478_build_po_draft_packet_review.py",
            expected_output="O local PO draft packet review lines, summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(line_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"source_action_rows={','.join(source_action_rows)};live_action_rows={','.join(live_action_rows)};"
                f"bad_summary_rows={','.join(bad_summary_rows)};live_language_rows={','.join(live_language_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};false_ready_rows={','.join(false_ready_rows)};"
                f"missing_block_reason_rows={','.join(missing_block_reason_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(line_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft packet review shows local packet shape without writing PO files or creating downstream actions.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft packet review proof only; no real PO, no purchase order file write, no purchase commitment, "
                "receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_hold_review_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_hold_review_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_hold_review_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_hold_review_health.csv"
    line_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    source_ready_state = "ready_for_local_po_draft_packet_review_only"
    held_state = "held_for_local_po_draft_review_only"
    blocked_state = "blocked_from_local_po_draft_hold_review"
    source_flag_columns = (
        "source_po_file_write_allowed",
        "source_po_creation_allowed",
        "source_purchase_commitment_allowed",
        "source_receiving_allowed",
        "source_send_to_amazon_allowed",
        "source_creates_live_action",
    )
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_source_rows: list[str] = []
    source_action_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_hold_rows: list[str] = []
    missing_hold_reason_rows: list[str] = []
    for idx, row in enumerate(line_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"line_{idx}"
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns):
            source_action_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(row_label)
        line_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("hold_review_line_state", "hold_review_reasons")
        )
        if any(token in line_text for token in unsafe_tokens):
            live_language_rows.append(row_label)
        state = _mot_text(row.get("hold_review_line_state", ""))
        if state not in {held_state, blocked_state}:
            unknown_state_rows.append(row_label)
        elif state == held_state and (
            _mot_text(row.get("po_draft_packet_review_id", "")) == ""
            or _mot_text(row.get("source_packet_review_line_state", "")) != source_ready_state
            or any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns)
            or _o_num(row.get("hold_order_qty", "")) is None
            or (_o_num(row.get("hold_order_qty", "")) or 0) <= 0
            or _o_num(row.get("hold_unit_cost_gbp", "")) is None
            or (_o_num(row.get("hold_unit_cost_gbp", "")) or 0) <= 0
            or _o_num(row.get("hold_line_value_gbp", "")) is None
            or (_o_num(row.get("hold_line_value_gbp", "")) or 0) <= 0
        ):
            false_hold_rows.append(row_label)
        if state in {held_state, blocked_state} and _mot_text(row.get("hold_review_reasons", "")) == "":
            missing_hold_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        hold_id = _mot_text(row.get("po_draft_hold_review_id", "")) or "missing_hold"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            bad_summary_rows.append(f"{hold_id}:action_flag")
        summary_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("hold_review_state", "hold_review_reasons")
        )
        if any(token in summary_text for token in unsafe_tokens):
            bad_summary_rows.append(f"{hold_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft hold review files are missing."
        manager_action = "Run the bounded O480 local PO draft hold review builder. Do not create POs or write PO hold files."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more PO draft hold review rows do not have an approved source class."
        manager_action = "Repair PO draft hold source labelling before using the preview."
    elif source_action_rows or live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = (
            f"source_action_rows={len(source_action_rows)};"
            f"live_action_rows={len(live_action_rows)};"
            f"bad_summary_rows={len(bad_summary_rows)};"
            f"live_language_rows={len(live_language_rows)}"
        )
        root_cause = "The PO draft hold review looks like a live PO, PO hold-file write, buying, receiving, or Amazon action."
        manager_action = "Keep PO draft hold review local-only and disconnected from existing PO and PO hold files."
    elif unknown_state_rows or false_hold_rows or missing_hold_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_hold_rows={len(false_hold_rows)};"
            f"missing_hold_reason_rows={len(missing_hold_reason_rows)}"
        )
        root_cause = "The PO draft hold review wording is unsafe or incomplete."
        manager_action = "Repair PO draft hold review logic before using the preview."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO draft hold review health file contains a non-ok check."
        manager_action = "Repair the PO draft hold review proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(line_rows)};summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft hold review is local-only and cannot create purchase orders or write PO hold files."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_hold_review",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O480_build_po_draft_hold_review.py",
            expected_output="O local PO draft hold review lines, summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(line_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"source_action_rows={','.join(source_action_rows)};live_action_rows={','.join(live_action_rows)};"
                f"bad_summary_rows={','.join(bad_summary_rows)};live_language_rows={','.join(live_language_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};false_hold_rows={','.join(false_hold_rows)};"
                f"missing_hold_reason_rows={','.join(missing_hold_reason_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(line_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft hold review shows local hold state without writing PO files or existing PO hold files.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft hold review proof only; no real PO, no purchase order file write, no purchase order hold-file write, "
                "no purchase commitment, receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_file_shape_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_file_shape_preview_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_file_shape_preview_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_file_shape_preview_health.csv"
    line_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_source_classes = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
    source_ready_state = "held_for_local_po_draft_review_only"
    ready_state = "ready_for_local_po_draft_file_shape_review_only"
    blocked_state = "blocked_from_local_po_draft_file_shape_review"
    source_flag_columns = (
        "source_po_file_write_allowed",
        "source_po_creation_allowed",
        "source_purchase_commitment_allowed",
        "source_receiving_allowed",
        "source_send_to_amazon_allowed",
        "source_creates_live_action",
    )
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_source_rows: list[str] = []
    source_action_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    for idx, row in enumerate(line_rows, start=1):
        row_label = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"line_{idx}"
        if _mot_text(row.get("source_class", "")) not in allowed_source_classes:
            invalid_source_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns):
            source_action_rows.append(row_label)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(row_label)
        line_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("file_shape_line_state", "file_shape_block_reasons")
        )
        if any(token in line_text for token in unsafe_tokens):
            live_language_rows.append(row_label)
        state = _mot_text(row.get("file_shape_line_state", ""))
        if state not in {ready_state, blocked_state}:
            unknown_state_rows.append(row_label)
        elif state == ready_state and (
            _mot_text(row.get("po_draft_hold_review_id", "")) == ""
            or _mot_text(row.get("source_hold_review_line_state", "")) != source_ready_state
            or any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns)
            or _o_num(row.get("file_shape_qty", "")) is None
            or (_o_num(row.get("file_shape_qty", "")) or 0) <= 0
            or _o_num(row.get("file_shape_unit_cost_gbp", "")) is None
            or (_o_num(row.get("file_shape_unit_cost_gbp", "")) or 0) <= 0
            or _o_num(row.get("file_shape_line_value_gbp", "")) is None
            or (_o_num(row.get("file_shape_line_value_gbp", "")) or 0) <= 0
        ):
            false_ready_rows.append(row_label)
        if state == blocked_state and _mot_text(row.get("file_shape_block_reasons", "")) == "":
            missing_block_reason_rows.append(row_label)

    bad_summary_rows: list[str] = []
    for row in summary_rows:
        preview_id = _mot_text(row.get("po_draft_file_shape_preview_id", "")) or "missing_shape"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            bad_summary_rows.append(f"{preview_id}:action_flag")
        summary_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("file_shape_state", "file_shape_block_reasons")
        )
        if any(token in summary_text for token in unsafe_tokens):
            bad_summary_rows.append(f"{preview_id}:live_language")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft file-shape preview files are missing."
        manager_action = "Run the bounded O482 local PO draft file-shape preview builder. Do not create POs or write PO files."
    elif invalid_source_rows:
        status = "fail"
        value = f"invalid_source_rows={len(invalid_source_rows)}"
        root_cause = "One or more PO draft file-shape preview rows do not have an approved source class."
        manager_action = "Repair PO draft file-shape source labelling before using the preview."
    elif source_action_rows or live_action_rows or bad_summary_rows or live_language_rows:
        status = "fail"
        value = (
            f"source_action_rows={len(source_action_rows)};"
            f"live_action_rows={len(live_action_rows)};"
            f"bad_summary_rows={len(bad_summary_rows)};"
            f"live_language_rows={len(live_language_rows)}"
        )
        root_cause = "The PO draft file-shape preview looks like a live PO, PO file write, buying, receiving, or Amazon action."
        manager_action = "Keep PO draft file-shape preview local-only and disconnected from existing PO files."
    elif unknown_state_rows or false_ready_rows or missing_block_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_block_reason_rows={len(missing_block_reason_rows)}"
        )
        root_cause = "The PO draft file-shape preview wording is unsafe or incomplete."
        manager_action = "Repair PO draft file-shape preview logic before using the preview."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO draft file-shape preview health file contains a non-ok check."
        manager_action = "Repair the PO draft file-shape proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(line_rows)};summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft file-shape preview is local-only and cannot create purchase orders or write PO files."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_file_shape_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O482_build_po_draft_file_shape_preview.py",
            expected_output="O local PO draft file-shape preview lines, summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(line_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_source_rows={','.join(invalid_source_rows)};"
                f"source_action_rows={','.join(source_action_rows)};live_action_rows={','.join(live_action_rows)};"
                f"bad_summary_rows={','.join(bad_summary_rows)};live_language_rows={','.join(live_language_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};false_ready_rows={','.join(false_ready_rows)};"
                f"missing_block_reason_rows={','.join(missing_block_reason_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(line_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft file-shape preview shows local file shape without writing PO files or existing PO hold files.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft file-shape preview proof only; no real PO, no purchase order file write, no purchase order hold-file write, "
                "no purchase commitment, receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_preview_construction_summary_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_preview_construction_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_preview_construction_summary_health.csv"
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    expected_stage_keys = {
        "po_draft_readiness",
        "po_line_design",
        "po_draft_packet_review",
        "po_draft_hold_review",
        "po_draft_file_shape",
    }
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    seen_stage_keys = {_mot_text(row.get("stage_key", "")) for row in summary_rows if _mot_text(row.get("stage_key", ""))}
    missing_stage_keys = sorted(expected_stage_keys - seen_stage_keys)
    extra_stage_keys = sorted(seen_stage_keys - expected_stage_keys)
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    stage_health_bad_rows: list[str] = []
    for idx, row in enumerate(summary_rows, start=1):
        stage_key = _mot_text(row.get("stage_key", "")) or f"stage_{idx}"
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(stage_key)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("stage_state", "stage_block_reasons")
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(stage_key)
        if _mot_text(row.get("health_bad_rows", "")) not in {"", "0"}:
            stage_health_bad_rows.append(stage_key)

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO preview construction summary files are missing."
        manager_action = "Run the bounded O484 local construction summary builder. Do not create POs or write PO files."
    elif missing_stage_keys or extra_stage_keys:
        status = "fail"
        value = f"missing_stage_keys={len(missing_stage_keys)};extra_stage_keys={len(extra_stage_keys)}"
        root_cause = "The O PO preview construction summary does not show exactly the approved local preview stages."
        manager_action = "Repair the construction summary stage map before using the UI view."
    elif live_action_rows or live_language_rows:
        status = "fail"
        value = f"live_action_rows={len(live_action_rows)};live_language_rows={len(live_language_rows)}"
        root_cause = "The O PO preview construction summary looks like a live PO, buying, receiving, or Amazon action."
        manager_action = "Keep the construction summary local-only and disconnected from existing PO files."
    elif stage_health_bad_rows or health_bad:
        status = "fail"
        value = f"stage_health_bad_rows={len(stage_health_bad_rows)};health_bad={len(health_bad)}"
        root_cause = "The O PO preview construction summary or one of its source stages has a non-ok health check."
        manager_action = "Repair the source-stage proof instead of masking the construction summary."
    else:
        status = "ok"
        value = f"summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO preview construction summary is local-only and cannot create purchase orders or write PO files."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_preview_construction_summary",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O484_build_po_preview_construction_summary.py",
            expected_output="One local O PO preview construction summary covers readiness, line design, packet review, hold review, and file-shape preview.",
            actual_proof=(
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};missing_stage_keys={','.join(missing_stage_keys)};"
                f"extra_stage_keys={','.join(extra_stage_keys)};live_action_rows={','.join(live_action_rows)};"
                f"live_language_rows={','.join(live_language_rows)};stage_health_bad_rows={','.join(stage_health_bad_rows)};"
                f"health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(summary_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO preview construction summary shows the local construction chain without claiming a live PO loop.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO preview construction summary proof only; no real PO, no purchase order file write, no purchase order hold-file write, "
                "no purchase commitment, receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_review_control_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    events_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_review_control_events.csv"
    controls_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_review_controls_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_review_controls_health.csv"
    event_rows = read_csv_rows(events_path)
    control_rows = read_csv_rows(controls_path)
    health_rows = read_csv_rows(health_path)
    paths = [events_path, controls_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_decision_states = {
        "local_po_draft_more_proof_needed",
        "local_po_draft_keep_on_hold",
        "local_po_draft_shape_ready_not_po",
    }
    allowed_control_states = {
        "waiting_for_local_po_draft_review_control",
        "blocked_file_shape_not_ready",
        "blocked_local_po_draft_control_stale",
        "blocked_false_local_po_draft_shape_ready",
        *allowed_decision_states,
    }
    ready_state = "local_po_draft_shape_ready_not_po"
    source_ready_state = "ready_for_local_po_draft_file_shape_review_only"
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_event_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_reason_rows: list[str] = []
    for idx, row in enumerate(event_rows, start=1):
        event_id = _mot_text(row.get("control_event_id", "")) or f"event_{idx}"
        decision_state = _mot_text(row.get("decision_state", ""))
        if decision_state not in allowed_decision_states:
            invalid_event_rows.append(event_id)
        if _mot_text(row.get("po_draft_file_shape_preview_id", "")) == "":
            invalid_event_rows.append(f"{event_id}:missing_shape")
        if _mot_text(row.get("decision_status", "")) != "local_po_draft_review_control":
            invalid_event_rows.append(f"{event_id}:bad_status")
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(event_id)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("decision_state", "decision_status", "decision_note", "event_source_reference")
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(event_id)

    for idx, row in enumerate(control_rows, start=1):
        preview_id = _mot_text(row.get("po_draft_file_shape_preview_id", "")) or f"control_{idx}"
        control_state = _mot_text(row.get("review_control_state", ""))
        if control_state not in allowed_control_states:
            unknown_state_rows.append(preview_id)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(preview_id)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("review_control_state", "review_control_reasons", "latest_decision_note")
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(preview_id)
        if control_state == ready_state and (
            _mot_text(row.get("source_file_shape_state", "")) != source_ready_state
            or _o_num(row.get("line_count", "")) is None
            or (_o_num(row.get("line_count", "")) or 0) <= 0
            or _mot_text(row.get("ready_line_count", "")) != _mot_text(row.get("line_count", ""))
            or _mot_text(row.get("blocked_line_count", "")) not in {"", "0"}
        ):
            false_ready_rows.append(preview_id)
        if control_state != ready_state and _mot_text(row.get("review_control_reasons", "")) == "":
            missing_reason_rows.append(preview_id)

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft review-control files are missing."
        manager_action = "Run the bounded O486 local PO draft review controls builder. Do not create POs or write PO files."
    elif invalid_event_rows:
        status = "fail"
        value = f"invalid_event_rows={len(invalid_event_rows)}"
        root_cause = "One or more PO draft review-control events are incomplete or unsupported."
        manager_action = "Repair local review-control event capture before using the controls."
    elif live_action_rows or live_language_rows:
        status = "fail"
        value = f"live_action_rows={len(live_action_rows)};live_language_rows={len(live_language_rows)}"
        root_cause = "The PO draft review controls look like a live PO, PO file write, buying, receiving, or Amazon action."
        manager_action = "Keep PO draft review controls local-only and disconnected from existing PO files."
    elif unknown_state_rows or false_ready_rows or missing_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_reason_rows={len(missing_reason_rows)}"
        )
        root_cause = "The PO draft review-control state is unsafe or incomplete."
        manager_action = "Repair PO draft review-control logic before using the control state."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO draft review controls health file contains a non-ok check."
        manager_action = "Repair the PO draft review controls proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"events={len(event_rows)};controls={len(control_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft review controls are local-only and cannot create purchase orders or write PO files."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_review_controls",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O486_build_po_draft_review_controls.py",
            expected_output="O local PO draft review-control events, current controls, and health proof remain local-only.",
            actual_proof=(
                f"events_exists={1 if events_path.exists() else 0};event_rows={len(event_rows)};"
                f"controls_exists={1 if controls_path.exists() else 0};control_rows={len(control_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_event_rows={','.join(invalid_event_rows)};"
                f"live_action_rows={','.join(live_action_rows)};live_language_rows={','.join(live_language_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};false_ready_rows={','.join(false_ready_rows)};"
                f"missing_reason_rows={','.join(missing_reason_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(control_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft review controls capture local decisions without claiming a live PO loop.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft review controls proof only; no real PO, no purchase order file write, no purchase order hold-file write, "
                "no purchase commitment, receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_export_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    lines_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_preview_lines_live.csv"
    summary_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_preview_summary_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_preview_health.csv"
    line_rows = read_csv_rows(lines_path)
    summary_rows = read_csv_rows(summary_path)
    health_rows = read_csv_rows(health_path)
    paths = [lines_path, summary_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    ready_state = "ready_for_local_po_draft_export_preview_only"
    blocked_state = "blocked_from_local_po_draft_export_preview"
    source_ready_state = "ready_for_local_po_draft_file_shape_review_only"
    control_ready_state = "local_po_draft_shape_ready_not_po"
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    source_flag_columns = tuple(f"source_{column}" for column in zero_flag_columns)
    control_flag_columns = tuple(f"control_{column}" for column in zero_flag_columns)
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    source_action_rows: list[str] = []
    control_action_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    bad_summary_rows: list[str] = []
    for idx, row in enumerate(line_rows, start=1):
        row_id = _mot_text(row.get("row_id", "")) or _mot_text(row.get("seller_sku", "")) or f"line_{idx}"
        state = _mot_text(row.get("export_preview_line_state", ""))
        if state not in {ready_state, blocked_state}:
            unknown_state_rows.append(row_id)
        if any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns):
            source_action_rows.append(row_id)
        if any(_mot_text(row.get(column, "")) != "0" for column in control_flag_columns):
            control_action_rows.append(row_id)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(row_id)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in (
                "source_review_control_state",
                "export_preview_line_state",
                "export_preview_block_reasons",
                "export_preview_basis",
            )
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(row_id)
        if state == ready_state and (
            _mot_text(row.get("po_draft_file_shape_preview_id", "")) == ""
            or _mot_text(row.get("source_file_shape_line_state", "")) != source_ready_state
            or _mot_text(row.get("source_review_control_state", "")) != control_ready_state
            or any(_mot_text(row.get(column, "")) != "0" for column in source_flag_columns)
            or any(_mot_text(row.get(column, "")) != "0" for column in control_flag_columns)
            or (_o_num(row.get("export_preview_qty", "")) or 0) <= 0
            or (_o_num(row.get("export_preview_unit_cost_gbp", "")) or 0) <= 0
            or (_o_num(row.get("export_preview_line_value_gbp", "")) or 0) <= 0
        ):
            false_ready_rows.append(row_id)
        if state == blocked_state and _mot_text(row.get("export_preview_block_reasons", "")) == "":
            missing_block_reason_rows.append(row_id)

    for idx, row in enumerate(summary_rows, start=1):
        summary_id = _mot_text(row.get("po_draft_export_preview_id", "")) or f"summary_{idx}"
        state = _mot_text(row.get("export_preview_state", ""))
        ready_count = _o_num(row.get("ready_line_count", ""))
        blocked_count = _o_num(row.get("blocked_line_count", ""))
        line_count = _o_num(row.get("line_count", ""))
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(summary_id)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("export_preview_state", "export_preview_block_reasons")
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(summary_id)
        if state not in {ready_state, blocked_state}:
            bad_summary_rows.append(f"{summary_id}:unknown_state")
        if (
            ready_count is None
            or blocked_count is None
            or line_count is None
            or int(ready_count + blocked_count) != int(line_count)
        ):
            bad_summary_rows.append(f"{summary_id}:count_mismatch")
        if state == ready_state and ((ready_count or 0) <= 0 or (blocked_count or 0) > 0):
            bad_summary_rows.append(f"{summary_id}:false_ready")

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft export-preview files are missing."
        manager_action = "Run the bounded O488 local PO draft export-preview builder. Do not create POs or write PO files."
    elif source_action_rows or control_action_rows or live_action_rows or live_language_rows:
        status = "fail"
        value = (
            f"source_action_rows={len(source_action_rows)};"
            f"control_action_rows={len(control_action_rows)};"
            f"live_action_rows={len(live_action_rows)};"
            f"live_language_rows={len(live_language_rows)}"
        )
        root_cause = "The PO draft export preview looks like a live PO, PO file write, buying, receiving, or Amazon action."
        manager_action = "Keep PO draft export preview local-only and disconnected from existing PO files."
    elif unknown_state_rows or false_ready_rows or missing_block_reason_rows or bad_summary_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_block_reason_rows={len(missing_block_reason_rows)};"
            f"bad_summary_rows={len(bad_summary_rows)}"
        )
        root_cause = "The PO draft export-preview state is unsafe or incomplete."
        manager_action = "Repair PO draft export-preview logic before using the preview state."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO draft export-preview health file contains a non-ok check."
        manager_action = "Repair the PO draft export-preview proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"lines={len(line_rows)};summary={len(summary_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft export preview is local-only and cannot create purchase orders or write PO files."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_export_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O488_build_po_draft_export_preview.py",
            expected_output="O local PO draft export-preview lines, summary, and health proof remain local-only.",
            actual_proof=(
                f"lines_exists={1 if lines_path.exists() else 0};line_rows={len(line_rows)};"
                f"summary_exists={1 if summary_path.exists() else 0};summary_rows={len(summary_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};source_action_rows={','.join(source_action_rows)};"
                f"control_action_rows={','.join(control_action_rows)};live_action_rows={','.join(live_action_rows)};"
                f"live_language_rows={','.join(live_language_rows)};unknown_state_rows={','.join(unknown_state_rows)};"
                f"false_ready_rows={','.join(false_ready_rows)};missing_block_reason_rows={','.join(missing_block_reason_rows)};"
                f"bad_summary_rows={','.join(bad_summary_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(line_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft export preview shows only a local export shape and does not claim a live PO loop.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft export-preview proof only; no real PO, no purchase order file write, no purchase order hold-file write, "
                "no purchase commitment, receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_po_draft_export_gate_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    events_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_gate_events.csv"
    gate_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_gate_live.csv"
    health_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_gate_health.csv"
    event_rows = read_csv_rows(events_path)
    gate_rows = read_csv_rows(gate_path)
    health_rows = read_csv_rows(health_path)
    paths = [events_path, gate_path, health_path]
    missing = [path.name for path in paths if not path.exists()]
    allowed_decision_states = {
        "local_export_more_proof_needed",
        "local_export_keep_on_hold",
        "local_export_candidate_ready_not_po",
    }
    allowed_gate_states = {
        "waiting_for_local_export_gate_control",
        "blocked_export_preview_not_ready",
        "blocked_local_export_gate_stale",
        "blocked_false_local_export_candidate_ready",
        *allowed_decision_states,
    }
    ready_state = "local_export_candidate_ready_not_po"
    source_ready_state = "ready_for_local_po_draft_export_preview_only"
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_tokens = (
        "purchase_order",
        "purchase order",
        "po_created",
        "po created",
        "committed",
        "sent_to_amazon",
        "sent to amazon",
        "buy_committed",
        "approval_applied",
        "live_action",
    )

    invalid_event_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_reason_rows: list[str] = []
    for idx, row in enumerate(event_rows, start=1):
        event_id = _mot_text(row.get("gate_event_id", "")) or f"event_{idx}"
        decision_state = _mot_text(row.get("decision_state", ""))
        if decision_state not in allowed_decision_states:
            invalid_event_rows.append(event_id)
        if _mot_text(row.get("po_draft_export_preview_id", "")) == "":
            invalid_event_rows.append(f"{event_id}:missing_export_preview")
        if _mot_text(row.get("decision_status", "")) != "local_po_draft_export_gate":
            invalid_event_rows.append(f"{event_id}:bad_status")
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(event_id)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("decision_state", "decision_status", "decision_note", "event_source_reference")
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(event_id)

    for idx, row in enumerate(gate_rows, start=1):
        preview_id = _mot_text(row.get("po_draft_export_preview_id", "")) or f"gate_{idx}"
        gate_state = _mot_text(row.get("export_gate_state", ""))
        if gate_state not in allowed_gate_states:
            unknown_state_rows.append(preview_id)
        if any(_mot_text(row.get(column, "")) != "0" for column in zero_flag_columns):
            live_action_rows.append(preview_id)
        row_text = " ".join(
            _mot_text(row.get(col, "")).lower()
            for col in ("export_gate_state", "export_gate_reasons", "latest_decision_note")
        )
        if any(token in row_text for token in unsafe_tokens):
            live_language_rows.append(preview_id)
        if gate_state == ready_state and (
            _mot_text(row.get("source_export_preview_state", "")) != source_ready_state
            or _o_num(row.get("line_count", "")) is None
            or (_o_num(row.get("line_count", "")) or 0) <= 0
            or _mot_text(row.get("ready_line_count", "")) != _mot_text(row.get("line_count", ""))
            or _mot_text(row.get("blocked_line_count", "")) not in {"", "0"}
        ):
            false_ready_rows.append(preview_id)
        if gate_state != ready_state and _mot_text(row.get("export_gate_reasons", "")) == "":
            missing_reason_rows.append(preview_id)

    health_bad = [row.get("check", "") for row in health_rows if _mot_text(row.get("status", "")).lower() not in {"", "ok"}]
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The O PO draft export-gate files are missing."
        manager_action = "Run the bounded O490 local PO draft export gate builder. Do not create POs or write PO files."
    elif invalid_event_rows:
        status = "fail"
        value = f"invalid_event_rows={len(invalid_event_rows)}"
        root_cause = "One or more PO draft export-gate events are incomplete or unsupported."
        manager_action = "Repair local export-gate event capture before using the gate."
    elif live_action_rows or live_language_rows:
        status = "fail"
        value = f"live_action_rows={len(live_action_rows)};live_language_rows={len(live_language_rows)}"
        root_cause = "The PO draft export gate looks like a live PO, PO file write, buying, receiving, or Amazon action."
        manager_action = "Keep PO draft export gate local-only and disconnected from existing PO files."
    elif unknown_state_rows or false_ready_rows or missing_reason_rows:
        status = "fail"
        value = (
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"missing_reason_rows={len(missing_reason_rows)}"
        )
        root_cause = "The PO draft export-gate state is unsafe or incomplete."
        manager_action = "Repair PO draft export-gate logic before using the gate state."
    elif health_bad:
        status = "fail"
        value = f"health_bad={len(health_bad)}"
        root_cause = "The PO draft export-gate health file contains a non-ok check."
        manager_action = "Repair the PO draft export-gate proof source instead of masking the UI output."
    else:
        status = "ok"
        value = f"events={len(event_rows)};gates={len(gate_rows)};health={len(health_rows)}"
        root_cause = ""
        manager_action = "No action; PO draft export gate is local-only and cannot create purchase orders or write PO files."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_po_draft_export_gate",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O490_build_po_draft_export_gate.py",
            expected_output="O local PO draft export-gate events, current gate state, and health proof remain local-only.",
            actual_proof=(
                f"events_exists={1 if events_path.exists() else 0};event_rows={len(event_rows)};"
                f"gates_exists={1 if gate_path.exists() else 0};gate_rows={len(gate_rows)};"
                f"health_exists={1 if health_path.exists() else 0};health_rows={len(health_rows)};"
                f"missing={','.join(missing)};invalid_event_rows={','.join(invalid_event_rows)};"
                f"live_action_rows={','.join(live_action_rows)};live_language_rows={','.join(live_language_rows)};"
                f"unknown_state_rows={','.join(unknown_state_rows)};false_ready_rows={','.join(false_ready_rows)};"
                f"missing_reason_rows={','.join(missing_reason_rows)};health_bad={','.join(health_bad)}"
            ),
            row_count=str(len(gate_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O PO draft export gate captures local candidate decisions without claiming a live PO loop.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "O PO draft export-gate proof only; no real PO, no purchase order file write, no purchase order hold-file write, "
                "no purchase commitment, receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_completion_claim_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    expectation_path = base / "project_control" / "EXPECTATIONS" / "operations_loop_expectations.md"
    complete_claims: list[str] = []
    if expectation_path.exists():
        for line in expectation_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or "---" in stripped:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) < 4 or cells[0].lower() == "feature":
                continue
            feature, status_text = cells[0], cells[2].lower()
            if status_text in {"complete", "done", "operational", "working", "live"}:
                complete_claims.append(feature)
    if not expectation_path.exists():
        status = "warn"
        value = "expectations_missing"
        root_cause = "O expectations file is missing."
        manager_action = "Restore the expectations file before making O completion claims."
    elif complete_claims:
        status = "fail"
        value = f"complete_claims={len(complete_claims)}"
        root_cause = "O expectations claim completion while the manager still sees bridge/proof-only/not-started stages."
        manager_action = "Remove or correct the completion claim before treating O as live."
    else:
        status = "ok"
        value = "mid_build_declared"
        root_cause = ""
        manager_action = "No action; O is still labelled as mid-build."
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_completion_claim_guard",
            status=status,
            severity=_severity(status),
            value=value,
            producer="operations_loop_expectations.md",
            expected_output="O must not be marked complete while major stages are bridge, proof-only, not started, or not verified.",
            actual_proof=f"complete_claims={','.join(complete_claims)};feature_count={len(O_FEATURE_STAGES)}",
            source_path=str(expectation_path),
            summary="The manager blocks accidental 'O is complete' wording until the full loop is proven.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="Manager wording and expectation mapping only; no worker repair.",
        )
    ]


def _o_real_po_readiness_gate_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    approval_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_guardrails_live.csv"
    controls_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_review_controls_live.csv"
    export_gate_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_gate_live.csv"
    review_rows = read_csv_rows(review_path)
    approval_rows = read_csv_rows(approval_path)
    control_rows = read_csv_rows(controls_path)
    export_gate_rows = read_csv_rows(export_gate_path)
    paths = [review_path, approval_path, controls_path, export_gate_path]
    missing = [path.name for path in paths if not path.exists()]
    ready_rows = [
        row for row in review_rows
        if _o_truthy(row.get("action_ready_now", ""))
        or _mot_text(row.get("row_status", "")).lower() in {"ready", "manual_review_ready", "review_ready"}
    ]
    blocked_rows = [
        row for row in review_rows
        if _mot_text(row.get("row_status", "")).lower() == "blocked"
    ]
    zero_flag_columns = (
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    )
    unsafe_sources: list[str] = []
    for label, rows in (
        ("approval", approval_rows),
        ("po_controls", control_rows),
        ("export_gate", export_gate_rows),
    ):
        for idx, row in enumerate(rows, start=1):
            row_id = (
                _mot_text(row.get("approval_guardrail_id", ""))
                or _mot_text(row.get("po_draft_review_control_id", ""))
                or _mot_text(row.get("po_draft_export_gate_id", ""))
                or _mot_text(row.get("po_draft_export_preview_id", ""))
                or f"{label}_{idx}"
            )
            for column in zero_flag_columns:
                if column in row and _o_truthy(row.get(column, "")):
                    unsafe_sources.append(f"{row_id}:{column}")

    approval_state = _mot_text(approval_rows[-1].get("approval_guardrail_state", "")) if approval_rows else ""
    po_control_state = _mot_text(control_rows[-1].get("review_control_state", "")) if control_rows else ""
    export_gate_state = _mot_text(export_gate_rows[-1].get("export_gate_state", "")) if export_gate_rows else ""
    ready_states_ok = (
        approval_state == "local_review_accept_not_commitment"
        and po_control_state == "local_po_draft_shape_ready_not_po"
        and export_gate_state == "local_export_candidate_ready_not_po"
        and len(ready_rows) > 0
    )
    closed_reasons: list[str] = []
    if not ready_rows:
        closed_reasons.append("no_clean_rows")
    if approval_state != "local_review_accept_not_commitment":
        closed_reasons.append("approval_guardrail_not_ready")
    if po_control_state != "local_po_draft_shape_ready_not_po":
        closed_reasons.append("po_review_control_not_ready")
    if export_gate_state != "local_export_candidate_ready_not_po":
        closed_reasons.append("po_export_gate_not_ready")

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The real-PO readiness gate is missing one or more source proof files."
        manager_action = "Rebuild the local O proof chain before considering real purchase-order readiness."
        luke_action_required = "0"
    elif unsafe_sources:
        status = "fail"
        value = f"unsafe_action_flags={len(unsafe_sources)}"
        root_cause = "A preview or gate row appears to allow a PO file write, purchase commitment, receiving, send-to-Amazon, or live action."
        manager_action = "Keep the real-PO gate closed and repair the source proof that exposed the unsafe flag."
        luke_action_required = "0"
    elif ready_states_ok:
        status = "decision_needed"
        value = f"ready_for_luke_decision;ready_rows={len(ready_rows)}"
        root_cause = "The local proof says the real-PO gate could move forward, but creating a purchase order is a protected business action."
        manager_action = "Luke must explicitly approve any real purchase-order creation path before O writes PO files or commits buying."
        luke_action_required = "1"
    else:
        status = "ok"
        value = f"closed;reasons={len(closed_reasons)};ready_rows={len(ready_rows)};blocked_rows={len(blocked_rows)}"
        root_cause = ""
        manager_action = "No action; the real-PO gate is closed safely while O is mid-build."
        luke_action_required = "0"

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_real_po_readiness_gate",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O manager real-PO readiness gate",
            expected_output="Real purchase-order creation stays closed until rows, approval guardrails, PO controls, export gate, and safety flags are all clean.",
            actual_proof=(
                f"review_rows={len(review_rows)};ready_rows={len(ready_rows)};blocked_rows={len(blocked_rows)};"
                f"approval_state={approval_state};po_control_state={po_control_state};export_gate_state={export_gate_state};"
                f"closed_reasons={','.join(closed_reasons)};unsafe_sources={','.join(unsafe_sources)};missing={','.join(missing)}"
            ),
            row_count=str(len(review_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O real-PO readiness is a closed/open gate, not a purchase-order action.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required=luke_action_required,
            safe_repair_boundary=(
                "Read-only readiness proof only; no real PO, PO file write, purchase commitment, receiving, send-to-Amazon, "
                "Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


O_REAL_PO_CLEARANCE_LANES = (
    "supplier_stock",
    "supplier_cost",
    "market_profit",
    "refund_inbound",
    "local_qty",
    "approval_po_gates",
)


def _o_real_po_clearance_lanes_for_row(row: dict[str, str]) -> set[str]:
    lanes: set[str] = set()
    block_text = "|".join(
        _mot_text(row.get(field, "")).lower()
        for field in ("action_block_reason", "missing_input_reasons", "profit_check_message", "operator_decision_state")
    )
    if (
        "supplier:" in block_text
        or "discontinued" in block_text
        or "supplier_stock" in block_text
        or _mot_text(row.get("supplier_stock_state", "")).lower() in {"", "supplier_stock_not_verified", "not_verified"}
        or _mot_text(row.get("supplier_match_state", "")).lower() in {"", "not_verified", "supplier_match_not_verified"}
        or _mot_text(row.get("backorder_state", "")).lower() in {"", "backorder_not_verified", "not_verified"}
        or _mot_text(row.get("supplier_file_asof_utc", "")) == ""
    ):
        lanes.add("supplier_stock")
    if (
        "supplier_cost" in block_text
        or "missing_supplier_cost" in block_text
        or _mot_text(row.get("supplier_cost_proof_state", "")).lower() in {"", "missing_supplier_cost", "supplier_cost_not_exact", "bridge_cost_only", "not_verified"}
        or _mot_text(row.get("current_supplier_cost_gbp", "")) == ""
    ):
        lanes.add("supplier_cost")
    profit_text = _mot_text(row.get("profit_check_message", "")).lower()
    if (
        "market_price" in block_text
        or "missing_market_price" in block_text
        or "missing_max_safe_cost" in block_text
        or "missing_forward_roi" in block_text
        or "missing_forward_profit" in block_text
        or "missing_net_fee_model" in block_text
        or "needs price check" in profit_text
        or "do not buy now" in profit_text
        or "test only" in profit_text
        or "drop review only" in profit_text
        or _mot_text(row.get("market_price_proof_state", "")).lower() in {"", "missing_current_market_price", "bridge_market_only", "not_verified"}
        or _mot_text(row.get("fee_proof_state", "")).lower() in {"", "fee_proof_missing", "not_verified"}
    ):
        lanes.add("market_profit")
    if (
        "refund:" in block_text
        or "inbound_cost:" in block_text
        or _mot_text(row.get("refund_proof_state", "")).lower() in {"", "missing_refund_confidence", "not_verified"}
        or _mot_text(row.get("inbound_cost_proof_state", "")).lower() in {"", "missing_inbound_cost_confidence", "not_verified"}
    ):
        lanes.add("refund_inbound")
    if (
        "order:" in block_text
        or _mot_text(row.get("order_qty_draft", "")) in {"", "0", "0.0"}
        or _mot_text(row.get("supplier_order_viability_state", "")).lower() in {"", "unknown_no_order_qty", "blocked_supplier_moq_too_low"}
    ):
        lanes.add("local_qty")
    return lanes


def _o_real_po_gate_clearance_worklist_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    approval_path = base / "out" / "systems" / "O" / "live" / "restock_purchase_approval_guardrails_live.csv"
    controls_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_review_controls_live.csv"
    export_gate_path = base / "out" / "systems" / "O" / "live" / "restock_po_draft_export_gate_live.csv"
    review_rows = read_csv_rows(review_path)
    approval_rows = read_csv_rows(approval_path)
    control_rows = read_csv_rows(controls_path)
    export_gate_rows = read_csv_rows(export_gate_path)
    paths = [review_path, approval_path, controls_path, export_gate_path]
    missing = [path.name for path in paths if not path.exists()]
    lane_counts = {lane: 0 for lane in O_REAL_PO_CLEARANCE_LANES}
    examples = {lane: [] for lane in O_REAL_PO_CLEARANCE_LANES}
    for row in review_rows:
        sku = _mot_text(row.get("seller_sku", "")) or _mot_text(row.get("asin", "")) or _mot_text(row.get("row_id", "")) or "row"
        for lane in _o_real_po_clearance_lanes_for_row(row):
            lane_counts[lane] += 1
            if len(examples[lane]) < 3 and sku not in examples[lane]:
                examples[lane].append(sku)

    approval_state = _mot_text(approval_rows[-1].get("approval_guardrail_state", "")) if approval_rows else ""
    po_control_state = _mot_text(control_rows[-1].get("review_control_state", "")) if control_rows else ""
    export_gate_state = _mot_text(export_gate_rows[-1].get("export_gate_state", "")) if export_gate_rows else ""
    if approval_state != "local_review_accept_not_commitment" or po_control_state != "local_po_draft_shape_ready_not_po" or export_gate_state != "local_export_candidate_ready_not_po":
        lane_counts["approval_po_gates"] = max(lane_counts["approval_po_gates"], len(review_rows))

    active_lanes = [lane for lane in O_REAL_PO_CLEARANCE_LANES if lane_counts[lane] > 0]
    if active_lanes:
        top_lane = sorted(active_lanes, key=lambda lane: (-lane_counts[lane], lane))[0]
    else:
        top_lane = ""
    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The real-PO gate clearance worklist is missing one or more source proof files."
        manager_action = "Rebuild the local O proof chain before using the real-PO gate worklist."
    elif review_rows and not active_lanes:
        status = "fail"
        value = "no_clearance_lanes"
        root_cause = "The real-PO gate is closed or rows exist, but the manager cannot see any clearance lanes."
        manager_action = "Repair blocker-lane classification before using O for real-PO readiness."
    else:
        status = "ok"
        lane_value = ";".join(f"{lane}={lane_counts[lane]}" for lane in O_REAL_PO_CLEARANCE_LANES)
        value = f"lanes={len(active_lanes)};top={top_lane};{lane_value}"
        root_cause = ""
        manager_action = "Use the worklist to clear proof lanes in O; do not create purchase orders until the real-PO gate opens and Luke approves."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_real_po_gate_clearance_worklist",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O manager real-PO gate clearance worklist",
            expected_output="A read-only lane count explains why the real-PO gate is closed and what proof lanes should clear next.",
            actual_proof=(
                f"review_rows={len(review_rows)};approval_state={approval_state};po_control_state={po_control_state};"
                f"export_gate_state={export_gate_state};lane_counts={';'.join(f'{lane}:{lane_counts[lane]}' for lane in O_REAL_PO_CLEARANCE_LANES)};"
                f"examples={';'.join(f'{lane}:{','.join(examples[lane])}' for lane in O_REAL_PO_CLEARANCE_LANES)};missing={','.join(missing)}"
            ),
            row_count=str(len(review_rows)),
            source_path=";".join(str(path) for path in paths),
            summary="O can now see the proof lanes that keep real purchase orders closed.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only gate-clearance proof only; no real PO, PO file write, purchase commitment, receiving, send-to-Amazon, "
                "Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_real_po_supplier_gate_clearance_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv"
    review_rows = read_csv_rows(review_path)
    missing = [] if review_path.exists() else [review_path.name]
    stock_rows = 0
    cost_rows = 0
    both_rows = 0
    stock_only_rows = 0
    cost_only_rows = 0
    supplier_clear_rows = 0
    examples = {
        "both": [],
        "stock_only": [],
        "cost_only": [],
    }
    for row in review_rows:
        lanes = _o_real_po_clearance_lanes_for_row(row)
        needs_stock = "supplier_stock" in lanes
        needs_cost = "supplier_cost" in lanes
        sku = _mot_text(row.get("seller_sku", "")) or _mot_text(row.get("asin", "")) or _mot_text(row.get("row_id", "")) or "row"
        if needs_stock:
            stock_rows += 1
        if needs_cost:
            cost_rows += 1
        if needs_stock and needs_cost:
            both_rows += 1
            if len(examples["both"]) < 3 and sku not in examples["both"]:
                examples["both"].append(sku)
        elif needs_stock:
            stock_only_rows += 1
            if len(examples["stock_only"]) < 3 and sku not in examples["stock_only"]:
                examples["stock_only"].append(sku)
        elif needs_cost:
            cost_only_rows += 1
            if len(examples["cost_only"]) < 3 and sku not in examples["cost_only"]:
                examples["cost_only"].append(sku)
        else:
            supplier_clear_rows += 1

    if missing:
        status = "fail"
        value = f"missing={len(missing)}"
        root_cause = "The supplier gate clearance panel is missing the restock review source file."
        manager_action = "Rebuild the local O restock session proof before using supplier gate clearance."
    else:
        status = "ok"
        value = (
            f"stock={stock_rows};cost={cost_rows};both={both_rows};"
            f"stock_only={stock_only_rows};cost_only={cost_only_rows};supplier_clear={supplier_clear_rows}"
        )
        root_cause = ""
        manager_action = "Use supplier gate clearance as a read-only guide for local supplier proof; do not fetch files, change supplier data, approve buying, or create purchase orders."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_real_po_supplier_gate_clearance",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O manager supplier gate clearance panel",
            expected_output="A read-only supplier lane breakdown shows stock proof, cost proof, both supplier lanes, and supplier-clear rows.",
            actual_proof=(
                f"review_rows={len(review_rows)};stock={stock_rows};cost={cost_rows};both={both_rows};"
                f"stock_only={stock_only_rows};cost_only={cost_only_rows};supplier_clear={supplier_clear_rows};"
                f"examples=both:{','.join(examples['both'])};stock_only:{','.join(examples['stock_only'])};"
                f"cost_only:{','.join(examples['cost_only'])};missing={','.join(missing)}"
            ),
            row_count=str(len(review_rows)),
            source_path=str(review_path),
            summary="O can see supplier stock and cost proof blockers without turning them into orders.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "Read-only supplier gate proof only; no supplier file fetch/change, real PO, PO file write, purchase commitment, "
                "receiving, send-to-Amazon, Sheet write, price change, queue edit, local DB alignment, H pause, market scan, or output deletion."
            ),
        )
    ]


def _o_h_market_gate_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    candidates_path = base / "out" / "systems" / "O" / "live" / "restock_market_refresh_candidates_live.csv"
    candidate_rows = read_csv_rows(candidates_path)
    ready_rows = [
        row for row in candidate_rows
        if _mot_text(row.get("candidate_status", "")).lower() == "ready"
    ]
    lock_paths = [
        base / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock",
        base / "out" / "H_pricing_cycle.lock",
    ]
    live_locks: list[str] = []
    lock_details: list[str] = []
    for path in lock_paths:
        fields = _read_lock_fields(path)
        if not fields:
            lock_details.append(f"{path}:missing")
            continue
        age_seconds = _lock_heartbeat_age_seconds(fields, now)
        live = age_seconds is not None and age_seconds < F_CHILD_FAIL_SECONDS
        pid_alive = _pid_alive(fields.get("pid", ""))
        if live:
            live_locks.append(str(path))
        lock_details.append(
            f"{path}:run_id={fields.get('run_id', '')}:age_seconds={_seconds_text(age_seconds)}:pid_alive={pid_alive}"
        )
    if not candidates_path.exists():
        status = "not_checked"
        value = "candidate_queue_missing"
        root_cause = "O market-refresh candidate queue is not present yet."
        manager_action = "Keep market refresh not verified until the candidate queue exists."
        luke_action_required = "0"
    elif ready_rows and live_locks:
        value = f"ready_candidates={len(ready_rows)};h_active=1"
        root_cause = "O has ready market-proof candidates, but H currently owns the market files."
        if controlled_technical_pause_allowed(base):
            status = "warn"
            manager_action = (
                "Create a manager-approved controlled proof packet: pause H only inside the packet, run the "
                "candidate-only market proof, then prove H scheduler ownership resumed."
            )
            luke_action_required = "0"
        elif quiet_autonomy_active(base):
            status = "not_checked"
            value = f"parked_until_h_controller_installed;ready_candidates={len(ready_rows)};h_active=1"
            manager_action = (
                "Park the O/H market-proof pause lane during Quiet Autonomy until the H maintenance controller "
                "install proof exists. Continue other approved manager work."
            )
            luke_action_required = "0"
        else:
            status = "decision_needed"
            manager_action = "Luke must approve the H pause/proof window before any controlled O market scan runs."
            luke_action_required = "1"
    else:
        status = "ok"
        value = f"ready_candidates={len(ready_rows)};h_active={1 if live_locks else 0}"
        root_cause = ""
        manager_action = "No action; no unsafe H/O market-proof overlap is currently requested."
        luke_action_required = "0"
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_h_market_proof_gate",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O021 market-refresh bridge / H pricing owner lock",
            expected_output="O market proof may run only inside a controlled proof packet that pauses and restores H safely.",
            actual_proof=f"candidate_rows={len(candidate_rows)};ready={len(ready_rows)};live_h_locks={len(live_locks)};locks={'|'.join(lock_details)}",
            row_count=str(len(candidate_rows)) if candidate_rows else "",
            source_path=f"{candidates_path};{';'.join(str(path) for path in lock_paths)}",
            summary="The O market-refresh bridge is gated by H ownership safety.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required=luke_action_required,
            safe_repair_boundary=(
                "Controlled technical H pause/resume and O candidate-only market proof are allowed only inside "
                "a manager-approved proof packet; no purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action."
            ),
        )
    ]


def _o_h_maintenance_controller_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    install_path = base / "out" / "locks" / "h_maintenance_controller_install_status.json"
    result_path = base / "out" / "locks" / "h_maintenance_controller_last_result.json"
    status_path = base / "out" / "systems" / "H" / "live" / "h_maintenance_controller_status.json"
    install = _read_json(install_path)
    result = _read_json(result_path)
    controller_status = _read_json(status_path)
    install_missing = [key for key in ("schema_version", "installed", "success", "failure_reason") if key not in install]
    result_missing = [key for key in ("schema_version", "controller", "success", "action", "forbidden_actions") if key not in result]

    installed = _o_truthy(install.get("installed", ""))
    install_success = _o_truthy(install.get("success", ""))
    result_success = _o_truthy(result.get("success", ""))
    failure_reason = _mot_text(install.get("failure_reason", ""))

    if not install_path.exists():
        status = "not_checked"
        value = "not_installed_or_not_proven"
        root_cause = "No H maintenance controller install proof exists yet."
        manager_action = "Keep H pause automation as not verified until the one-time Administrator install writes proof."
        luke_action_required = "0"
    elif install.get("_read_error"):
        status = "warn"
        value = "install_status_unreadable"
        root_cause = "The H maintenance controller install proof cannot be read."
        manager_action = "Inspect the install proof file before using controller-based pause requests."
        luke_action_required = "0"
    elif failure_reason == "administrator_required" and not installed:
        if quiet_autonomy_active(base):
            status = "not_checked"
            value = "admin_install_required_parked_quiet_autonomy"
            manager_action = (
                "Park H pause/resume automation during Quiet Autonomy until the one-time Administrator install "
                "is completed. Continue other approved manager work."
            )
            luke_action_required = "0"
        else:
            status = "decision_needed"
            value = "admin_install_required"
            manager_action = "Luke must run the one-time H maintenance controller installer as Administrator before Codex can automate H pause/resume requests."
            luke_action_required = "1"
        root_cause = "The controller installer was tested from a non-admin shell and correctly refused to install."
    elif install_missing:
        status = "warn"
        value = f"install_schema_missing={len(install_missing)}"
        root_cause = "The H maintenance controller install proof is missing required fields."
        manager_action = "Repair the install proof schema before trusting controller automation."
        luke_action_required = "0"
    elif not installed or not install_success:
        if quiet_autonomy_active(base):
            status = "not_checked"
            value = f"controller_install_not_proven_parked_quiet_autonomy:{failure_reason or 'unknown'}"
            manager_action = (
                "Park H pause/resume automation during Quiet Autonomy until clean H maintenance controller "
                "install proof exists. Continue other approved manager work."
            )
            luke_action_required = "0"
        else:
            status = "warn"
            value = f"install_failed:{failure_reason or 'unknown'}"
            manager_action = "Repair the installer or rerun it from the correct Administrator shell before using controller requests."
            luke_action_required = "0"
        root_cause = "The H maintenance controller install proof says installation failed."
    elif result_path.exists() and result.get("_read_error"):
        status = "warn"
        value = "last_result_unreadable"
        root_cause = "The H maintenance controller last-result proof cannot be read."
        manager_action = "Inspect the controller result proof before using another H maintenance request."
        luke_action_required = "0"
    elif result_path.exists() and result_missing:
        status = "warn"
        value = f"result_schema_missing={len(result_missing)}"
        root_cause = "The H maintenance controller result proof is missing required fields."
        manager_action = "Repair the controller result schema before trusting pause/resume automation."
        luke_action_required = "0"
    elif result_path.exists() and not result_success:
        status = "warn"
        value = f"last_result_failed:{_mot_text(result.get('failure_reason', '')) or 'unknown'}"
        root_cause = "The latest H maintenance controller request did not succeed."
        manager_action = "Inspect the controller result and only retry inside an approved proof packet."
        luke_action_required = "0"
    else:
        status = "ok"
        value = "installed"
        root_cause = ""
        manager_action = "No action; H pause/resume automation has install proof and remains bounded to controller requests."
        luke_action_required = "0"

    status_state = _mot_text(controller_status.get("state", "")) or _mot_text(controller_status.get("action", ""))
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_h_maintenance_controller_gate",
            status=status,
            severity=_severity(status),
            value=value,
            producer="H200_request_h_maintenance.py / h_maintenance_controller.ps1",
            expected_output="Admin-gated H maintenance controller proof with bounded status/pause/resume actions only.",
            actual_proof=(
                f"install_exists={1 if install_path.exists() else 0};installed={installed};install_success={install_success};"
                f"install_missing={','.join(install_missing)};result_exists={1 if result_path.exists() else 0};"
                f"result_success={result_success};result_missing={','.join(result_missing)};controller_status={status_state}"
            ),
            source_path=f"{install_path};{result_path};{status_path}",
            summary="H maintenance automation is allowed only through a one-time admin-installed controller and bounded request files.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required=luke_action_required,
            safe_repair_boundary=(
                "Controller proof only; no H pause/resume unless an approved proof packet exists, and no market scan, "
                "purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action."
            ),
        )
    ]


def _o_user_working_readiness_rows(*, base: Path, observed_utc: str, existing_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows_by_check = {row.get("check", ""): row for row in existing_rows}
    safety_blockers: list[str] = []
    tolerated_warnings: list[str] = []

    for check in O_USER_WORKING_REQUIRED_CHECKS:
        row = rows_by_check.get(check)
        if not row:
            safety_blockers.append(f"{check}:missing")
            continue
        row_status = row.get("status", "")
        if row_status == "ok":
            continue
        if row_status == "warn" and check in O_USER_WORKING_REQUIRED_WARN_OK_CHECKS:
            tolerated_warnings.append(f"{check}:{row_status}:{row.get('value', '')}")
            continue
        safety_blockers.append(f"{check}:{row_status}")

    for check in O_USER_WORKING_TOLERATED_WARN_CHECKS:
        row = rows_by_check.get(check)
        if not row:
            continue
        if row.get("status") == "fail" or row.get("luke_action_required") == "1":
            safety_blockers.append(f"{check}:{row.get('status', '') or 'luke_action'}")
        elif row.get("status") != "ok":
            tolerated_warnings.append(f"{check}:{row.get('status', '')}:{row.get('value', '')}")

    missing_ui_files = [rel for rel in O_USER_WORKING_UI_FILES if not (base / rel).exists()]
    product_view_path = base / "out" / "systems" / "O" / "live" / "product_db_operator_view.csv"
    product_view_rows = csv_row_count(product_view_path) if product_view_path.exists() else None
    if missing_ui_files:
        safety_blockers.append(f"missing_ui_files={len(missing_ui_files)}")
    if product_view_rows is None:
        safety_blockers.append("product_db_operator_view:missing_or_unreadable")
    elif product_view_rows <= 0:
        safety_blockers.append("product_db_operator_view:empty")

    if safety_blockers:
        status = "fail"
        value = f"not_ready;safety_blockers={len(safety_blockers)};tolerated_warnings={len(tolerated_warnings)}"
        root_cause = "O is not safe enough for a user walkthrough because a built safety or UI proof is missing or failing."
        manager_action = "Create a bounded O user-working repair packet. Do not run H pause, market scans, PO, receiving, send-to-Amazon, Sheets, prices, queues, DB alignment, or output deletion."
    else:
        status = "ok"
        value = f"ready_for_user_work;tolerated_warnings={len(tolerated_warnings)};product_rows={product_view_rows}"
        root_cause = ""
        manager_action = "Use O for a user walkthrough of viewing, review, and decision-shaping only. Keep buy/PO/receiving/Amazon actions blocked."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="O",
            check="o_user_working_readiness",
            status=status,
            severity=_severity(status),
            value=value,
            producer="O manager readiness gate",
            expected_output="O is safe for user walkthrough work without claiming the full operations loop is live.",
            actual_proof=(
                f"required_checks={','.join(O_USER_WORKING_REQUIRED_CHECKS)};"
                f"safety_blockers={';'.join(safety_blockers)};"
                f"tolerated_warnings={';'.join(tolerated_warnings)};"
                f"missing_ui_files={','.join(missing_ui_files)};"
                f"product_db_operator_view_rows={product_view_rows if product_view_rows is not None else ''}"
            ),
            row_count=str(product_view_rows or ""),
            source_path=";".join([str(base / rel) for rel in O_USER_WORKING_UI_FILES] + [str(product_view_path)]),
            summary="O is judged ready for user-facing build work only when the safety guardrails and UI/viewing proof are present.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary=(
                "User walkthrough and manager proof only; no purchase commitment, PO creation, receiving action, "
                "send-to-Amazon action, Sheet write, price change, queue edit, DB alignment, output deletion, H pause, or market scan."
            ),
        )
    ]


def build_o_hourly_mot(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    rows: list[dict[str, str]] = []

    rows.extend(_o_stage_map_rows(observed_utc=observed))
    rows.extend(_o_proof_file_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_o_refund_restock_confidence_rows(base=base, observed_utc=observed))
    rows.extend(_o_inbound_fba_cost_proof_rows(base=base, observed_utc=observed))
    rows.extend(_o_profit_input_blocker_breakdown_rows(base=base, observed_utc=observed))
    rows.extend(_o_inbound_fba_source_options_rows(base=base, observed_utc=observed))
    rows.extend(_o_token_cost_trust_gate_rows(base=base, observed_utc=observed))
    rows.extend(_o_buy_guardrail_rows(base=base, observed_utc=observed))
    rows.extend(_o_legacy_bridge_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_source_rows(base=base, observed_utc=observed))
    rows.extend(_o_receiving_send_rows(base=base, observed_utc=observed))
    rows.extend(_o_restock_session_rows(base=base, observed_utc=observed))
    rows.extend(_o_restock_supplier_batch_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_file_source_index_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_file_presence_probe_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_file_evidence_visibility_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_file_proof_coverage_map_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_proof_work_queue_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_proof_queue_filter_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_proof_action_workbench_rows(base=base, observed_utc=observed))
    rows.extend(_o_supplier_proof_field_focus_filter_rows(base=base, observed_utc=observed))
    rows.extend(_o_purchase_approval_preview_rows(base=base, observed_utc=observed))
    rows.extend(_o_purchase_approval_guardrail_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_readiness_preview_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_line_design_preview_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_packet_review_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_hold_review_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_file_shape_preview_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_preview_construction_summary_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_review_control_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_export_preview_rows(base=base, observed_utc=observed))
    rows.extend(_o_po_draft_export_gate_rows(base=base, observed_utc=observed))
    rows.extend(_o_real_po_readiness_gate_rows(base=base, observed_utc=observed))
    rows.extend(_o_real_po_gate_clearance_worklist_rows(base=base, observed_utc=observed))
    rows.extend(_o_real_po_supplier_gate_clearance_rows(base=base, observed_utc=observed))
    rows.extend(_o_completion_claim_rows(base=base, observed_utc=observed))
    rows.extend(_o_h_maintenance_controller_rows(base=base, observed_utc=observed))
    rows.extend(_o_h_market_gate_rows(base=base, observed_utc=observed, now=now))
    rows.extend(_o_user_working_readiness_rows(base=base, observed_utc=observed, existing_rows=rows))
    return _result_from_rows(observed, "O", rows)


def _result_from_rows(observed: str, flow: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    fail_count = sum(1 for row in rows if row["status"] == "fail")
    warn_count = sum(1 for row in rows if row["status"] == "warn")
    decision_count = sum(1 for row in rows if row["status"] == "decision_needed" or row.get("luke_action_required") == "1")
    not_checked_count = sum(1 for row in rows if row["status"] == "not_checked")
    status = "decision_needed" if decision_count else "fail" if fail_count else "warn" if warn_count else "ok"
    return {
        "observed_utc": observed,
        "flow": flow,
        "status": status,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "decision_count": decision_count,
        "not_checked_count": not_checked_count,
        "rows": rows,
    }


def build_hourly_mot_for_flow(
    flow: str,
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    mot_flow = str(flow or "").strip().upper()
    if mot_flow == "A":
        return build_a_hourly_mot(root=root, observed_utc=observed_utc)
    if mot_flow == "B":
        return build_b_hourly_mot(root=root, observed_utc=observed_utc)
    if mot_flow == "E":
        return build_e_hourly_mot(root=root, observed_utc=observed_utc)
    if mot_flow == "H":
        return build_h_hourly_mot(root=root, observed_utc=observed_utc)
    if mot_flow == "F":
        return build_f_hourly_mot(root=root, observed_utc=observed_utc)
    if mot_flow == "O":
        return build_o_hourly_mot(root=root, observed_utc=observed_utc)
    raise ValueError(f"unsupported MOT flow: {flow}")


def build_all_hourly_mot(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> list[dict[str, Any]]:
    return [
        build_hourly_mot_for_flow(flow, root=root, observed_utc=observed_utc)
        for flow in SUPPORTED_MOT_FLOWS
    ]


def _sql_table_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    db_path = _sqlite_path(base)
    rows: list[dict[str, str]] = []
    if not db_path.exists():
        return [
            mot_row(
                observed_utc=observed_utc,
                check="a_sqlite_database",
                status="warn",
                severity="warning",
                value="missing",
                producer="local SQLite store",
                expected_output="out/sql/sellerone_dev.sqlite3",
                actual_proof="database_missing",
                source_path=str(db_path),
                summary="The local SQLite database was not found, so SQL-side A proof could not be checked.",
                root_cause_guess="SQL proof unavailable.",
                manager_action="Keep CSV proof available, then decide whether SQL proof is mandatory for this machine.",
                safe_repair_boundary="Manager proof only; no DB alignment or backfill.",
            )
        ]
    try:
        con = sqlite3.connect(str(db_path))
    except sqlite3.Error as exc:
        return [
            mot_row(
                observed_utc=observed_utc,
                check="a_sqlite_database",
                status="fail",
                severity="blocker",
                value="open_failed",
                producer="local SQLite store",
                expected_output="out/sql/sellerone_dev.sqlite3",
                actual_proof=f"open_failed:{exc.__class__.__name__}",
                source_path=str(db_path),
                summary=f"SQLite database could not be opened: {exc.__class__.__name__}.",
                root_cause_guess="SQL proof database cannot be opened.",
                manager_action="Create a Codex task to inspect database availability before trusting SQL-backed A outputs.",
                safe_repair_boundary="Manager proof only; no DB alignment or backfill.",
            )
        ]
    try:
        for check, table in A_SQL_TABLES:
            try:
                table_row = con.execute(
                    "select name from sqlite_master where type='table' and name=?",
                    (table,),
                ).fetchone()
                if table_row is None:
                    status = "fail"
                    count_text = ""
                    value = "missing_table"
                    root_cause = "Expected SQL table is missing."
                else:
                    count = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                    status = "ok" if count > 0 else "fail"
                    count_text = str(count)
                    value = "rows_present" if count > 0 else "empty_table"
                    root_cause = "" if count > 0 else "Expected SQL table exists but is empty."
            except sqlite3.Error as exc:
                status = "fail"
                count_text = ""
                value = f"read_error:{exc.__class__.__name__}"
                root_cause = "Expected SQL table could not be read."
            rows.append(
                mot_row(
                    observed_utc=observed_utc,
                    check=check,
                    status=status,
                    severity=_severity(status),
                    value=value,
                    producer="local SQLite store",
                    expected_output=table,
                    actual_proof=f"table={table};rows={count_text};value={value}",
                    row_count=count_text,
                    source_path=f"{db_path}::{table}",
                    summary=f"SQL table `{table}` should contain the A output copy used by database-backed flows.",
                    root_cause_guess=root_cause,
                    manager_action="If fail, do not assume the CSV copy reached the database-backed path.",
                    safe_repair_boundary="Manager proof only; no DB alignment or backfill.",
                )
            )
    finally:
        con.close()
    return rows


def _sqlite_path(base: Path) -> Path:
    db_path = Path(os.environ.get("SELLERONE_SQLITE_PATH", str(base / "out" / "sql" / "sellerone_dev.sqlite3")))
    return db_path if db_path.is_absolute() else base / db_path


def _proof_only_output_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in A_PROOF_ONLY_OUTPUTS:
        path = base / item["path"]
        age = file_age_hours(path, now)
        rows_count = csv_row_count(path)
        min_rows = int(item.get("min_rows", 0) or 0)
        if rows_count is None:
            status = "not_checked"
            value = "missing"
            root_cause = "Proof-only A018 floor table is not available yet."
        elif rows_count < min_rows:
            status = "not_checked"
            value = f"rows_below_min:{rows_count}<{min_rows}"
            root_cause = "Proof-only A018 floor table exists but is empty."
        elif status_from_age(age, warn_hours=A_DAILY_WARN_HOURS, fail_hours=A_DAILY_FAIL_HOURS) != "ok":
            status = "not_checked"
            value = "stale"
            root_cause = "Proof-only A018 floor table is stale."
        else:
            status = "ok"
            value = "fresh_enough"
            root_cause = ""
        rows.append(
            mot_row(
                observed_utc=observed_utc,
                check=str(item["check"]),
                status=status,
                severity=_severity(status),
                value=value,
                producer=str(item["producer"]),
                expected_output=str(item["path"]),
                actual_proof=f"exists={1 if path.exists() else 0};rows={'' if rows_count is None else rows_count};age_hours={_age_text(age)}",
                age_hours=_age_text(age),
                row_count="" if rows_count is None else str(rows_count),
                source_path=str(path),
                summary=str(item["summary"]),
                root_cause_guess=root_cause,
                manager_action="Keep A018 as proof-only for this batch; do not start an A repair from this row alone.",
                safe_repair_boundary=str(item["safe_repair_boundary"]),
            )
        )
    return rows


def _proof_only_sql_table_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    db_path = _sqlite_path(base)
    if not db_path.exists():
        return [
            mot_row(
                observed_utc=observed_utc,
                check=check,
                status="not_checked",
                severity="info",
                value="database_missing",
                producer="local SQLite store",
                expected_output=table,
                actual_proof="database_missing",
                source_path=f"{db_path}::{table}",
                summary=f"Optional proof-only SQL table `{table}` could not be checked because the local database is missing.",
                root_cause_guess="Proof-only SQL evidence is unavailable.",
                manager_action="Keep this as not_verified proof coverage, not an A runtime failure.",
                safe_repair_boundary="Manager proof only; no DB alignment or backfill.",
            )
            for check, table in A_PROOF_ONLY_SQL_TABLES
        ]
    rows: list[dict[str, str]] = []
    try:
        con = sqlite3.connect(str(db_path))
    except sqlite3.Error as exc:
        return [
            mot_row(
                observed_utc=observed_utc,
                check=check,
                status="not_checked",
                severity="info",
                value=f"open_failed:{exc.__class__.__name__}",
                producer="local SQLite store",
                expected_output=table,
                actual_proof=f"open_failed:{exc.__class__.__name__}",
                source_path=f"{db_path}::{table}",
                summary=f"Optional proof-only SQL table `{table}` could not be checked.",
                root_cause_guess="Proof-only SQL evidence is unavailable.",
                manager_action="Keep this as not_verified proof coverage, not an A runtime failure.",
                safe_repair_boundary="Manager proof only; no DB alignment or backfill.",
            )
            for check, table in A_PROOF_ONLY_SQL_TABLES
        ]
    try:
        for check, table in A_PROOF_ONLY_SQL_TABLES:
            try:
                table_row = con.execute(
                    "select name from sqlite_master where type='table' and name=?",
                    (table,),
                ).fetchone()
                if table_row is None:
                    status = "not_checked"
                    count_text = ""
                    value = "missing_table"
                    root_cause = "Optional proof-only SQL table is missing."
                else:
                    count = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                    status = "ok" if count > 0 else "not_checked"
                    count_text = str(count)
                    value = "rows_present" if count > 0 else "empty_table"
                    root_cause = "" if count > 0 else "Optional proof-only SQL table is empty."
            except sqlite3.Error as exc:
                status = "not_checked"
                count_text = ""
                value = f"read_error:{exc.__class__.__name__}"
                root_cause = "Optional proof-only SQL table could not be read."
            rows.append(
                mot_row(
                    observed_utc=observed_utc,
                    check=check,
                    status=status,
                    severity=_severity(status),
                    value=value,
                    producer="local SQLite store",
                    expected_output=table,
                    actual_proof=f"table={table};rows={count_text};value={value}",
                    row_count=count_text,
                    source_path=f"{db_path}::{table}",
                    summary=f"Optional proof-only SQL table `{table}` supports the A018 floor table proof.",
                    root_cause_guess=root_cause,
                    manager_action="Keep this as proof-only coverage; do not align or backfill DB from MOT.",
                    safe_repair_boundary="Manager proof only; no DB alignment or backfill.",
                )
            )
    finally:
        con.close()
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_read_error": "1"}
    return payload if isinstance(payload, dict) else {"_read_error": "1"}


def _b_manifest_rows(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    manifest: dict[str, Any],
    manifest_path: Path | None,
) -> list[dict[str, str]]:
    if not manifest_path:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_latest_manifest",
                status="fail",
                severity="blocker",
                value="missing",
                producer="scripts/cycles/run_B_cycle.py",
                expected_output="out/manifests/B/**/*.json",
                actual_proof="manifest_missing",
                source_path=str(base / "out" / "manifests" / "B"),
                summary="No B manifest was found, so the manager cannot prove a B loop completed.",
                root_cause_guess="B has no durable run proof.",
                manager_action="Create a bounded B manager task to inspect B proof writing before trusting B state.",
                safe_repair_boundary="B proof inspection only; do not run or restart B from MOT.",
            )
        ]

    end_time = parse_utc(str(manifest.get("end_time", "")))
    age = max((now - end_time).total_seconds() / 3600.0, 0.0) if end_time else file_age_hours(manifest_path, now)
    final_state = str(manifest.get("final_state", "") or "unknown")
    manifest_status = status_from_age(age, warn_hours=B_MANIFEST_WARN_HOURS, fail_hours=B_MANIFEST_FAIL_HOURS)
    if final_state not in {"completed", "success"}:
        manifest_status = "fail"

    gate_state = str(manifest.get("gate_state", "") or "unknown")
    gate_fail_count = int(manifest.get("gate_fail_count", 0) or 0)
    gate_warn_count = int(manifest.get("gate_warn_count", 0) or 0)
    gate_status = "not_checked"
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_latest_manifest",
            status=manifest_status,
            severity=_severity(manifest_status),
            value=final_state,
            producer="scripts/cycles/run_B_cycle.py",
            expected_output="out/manifests/B/**/*.json",
            actual_proof=f"manifest_age_hours={_age_text(age)};final_state={final_state}",
            age_hours=_age_text(age),
            source_path=str(manifest_path),
            summary="Latest B manifest proves whether a B loop reached a terminal state and how old that proof is.",
            root_cause_guess="B manifest is stale or not completed." if manifest_status != "ok" else "",
            manager_action="If fail, inspect B proof state before trusting B outputs. Do not run or restart B from MOT.",
            safe_repair_boundary="B manifest proof only; no B run, restart, or output deletion.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_manifest_gate",
            status=gate_status,
            severity=_severity(gate_status),
            value=gate_state,
            producer="scripts/cycles/run_B_cycle.py",
            expected_output="B manifest gate fields",
            actual_proof=f"gate_state={gate_state};fail_count={gate_fail_count};warn_count={gate_warn_count}",
            source_path=str(manifest_path),
            summary="B gate result is a clue only because it can repeat old checklist FAIL/WARN state.",
            root_cause_guess=(
                "B manifest recorded a gate warning or failure; use independent MOT rows to prove the real condition."
                if gate_state == "fail" or gate_fail_count or gate_warn_count
                else ""
            ),
            manager_action="Use this as triage context only. Do not repair B from this row alone.",
            safe_repair_boundary="B gate clue only; no B run, restart, Sheet write, or data correction from MOT.",
        ),
    ]


def _b_required_output_rows(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    manifest: dict[str, Any] | None = None,
    manifest_path: Path | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    token_shortage_path = base / "out" / "token_shortages_by_sku.csv"
    protected_shortage_summary = _b_protected_token_shortage_summary(token_shortage_path)
    for item in B_REQUIRED_OUTPUTS:
        path = base / item["path"]
        age = file_age_hours(path, now)
        rows_count = csv_row_count(path)
        min_rows = int(item.get("min_rows", 0) or 0)
        status = status_from_age(age, warn_hours=float(item["warn_hours"]), fail_hours=float(item["fail_hours"]))
        root_cause = ""
        if rows_count is None:
            status = "fail"
            value = "missing_or_unreadable"
            root_cause = "Expected B output is missing or cannot be read."
        elif rows_count < min_rows:
            status = "fail"
            value = f"rows_below_min:{rows_count}<{min_rows}"
            root_cause = "Expected B output exists but has too few rows."
        else:
            value = "fresh_enough" if status == "ok" else "stale"
            if status != "ok":
                root_cause = "Expected B output is stale."
        manager_action = "If fail, create a bounded B repair task for the producer path. Do not run B or correct data from MOT."
        actual_proof = f"exists={1 if path.exists() else 0};rows={'' if rows_count is None else rows_count};age_hours={_age_text(age)}"
        source_path = str(path)
        luke_action_required = "0"
        safe_repair_boundary = str(item["safe_repair_boundary"])
        if item["check"] == "b_pnl_daily":
            d001_step_seen = any(
                "d001_build_pnl_daily.py" in str(step.get("name", "") or step.get("script_or_function", "")).lower()
                for step in (manifest or {}).get("steps", [])
                if isinstance(step, dict)
            )
            actual_proof = f"{actual_proof};d001_step_seen={1 if d001_step_seen else 0}"
            if status == "warn":
                root_cause = (
                    "P and L exists but is older than the manager warning window. "
                    "This is waiting producer refresh proof, not a MOT-side finance repair."
                )
                manager_action = (
                    "Keep P and L warning-labelled until the normal producer refreshes it. "
                    "Do not run D001, run B, or rewrite finance data from MOT."
                )
        if item["check"] == "b_pnl_daily" and status == "fail":
            gate_state = str((manifest or {}).get("gate_state", "") or "")
            gate_fail_count = int((manifest or {}).get("gate_fail_count", 0) or 0)
            if (gate_state == "fail" or gate_fail_count > 0) and not d001_step_seen:
                value = "blocked_by_b_health_gate"
                root_cause = (
                    "Latest B run skipped P and L publish because the B health gate was failing. "
                    "Current gate proof must be fixed before P and L freshness can clear."
                )
                manager_action = (
                    "Create or continue a bounded B gate/token-shortage proof task. "
                    "Do not run D001, run B, write Sheets, or correct finance data from MOT."
                )
                actual_proof = (
                    f"{actual_proof};manifest_gate_state={gate_state};"
                    f"manifest_gate_fail_count={gate_fail_count}"
                )
                if manifest_path:
                    source_path = f"{path};{manifest_path}"
                if protected_shortage_summary:
                    status = "decision_needed"
                    value = "blocked_by_protected_token_shortage"
                    root_cause = (
                        "Latest B run skipped P and L because B found a true live token or stock shortage. "
                        "That is a stock decision, not a safe code repair."
                    )
                    manager_action = (
                        "Stop B P and L repair work. Luke must choose whether to wait for receipt evidence "
                        "or approve a bounded stock/token correction. Do not run D001, run B, write Sheets, "
                        "align local DB data, or correct stock/token data from MOT."
                    )
                    actual_proof = f"{actual_proof};protected_token_shortage={protected_shortage_summary}"
                    source_path = f"{source_path};{token_shortage_path}"
                    luke_action_required = "1"
                    safe_repair_boundary = (
                        "Decision proof only; no B run, D001 run, token correction, stock correction, Sheet write, "
                        "local DB alignment, output deletion, price change, queue edit, or downstream masking without Luke approval."
                    )
        rows.append(
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check=str(item["check"]),
                status=status,
                severity=_severity(status),
                value=value,
                producer=str(item["producer"]),
                expected_output=str(item["path"]),
                actual_proof=actual_proof,
                age_hours=_age_text(age),
                row_count="" if rows_count is None else str(rows_count),
                source_path=source_path,
                summary=str(item["summary"]),
                root_cause_guess=root_cause,
                manager_action=manager_action,
                luke_action_required=luke_action_required,
                safe_repair_boundary=safe_repair_boundary,
            )
        )
    return rows


def _csv_value(row: dict[str, str], candidates: list[str]) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for candidate in candidates:
        value = lowered.get(str(candidate).strip().lower())
        if value is not None:
            return str(value or "").strip()
    return ""


def _csv_has_columns(path: Path, required: list[str]) -> bool:
    headers = csv_headers(path)
    if headers is None:
        return False
    header_set = {str(key).strip().lower() for key in headers}
    return all(str(column).strip().lower() in header_set for column in required)


def _b_latest_a_receipt_step(base: Path) -> tuple[dict[str, Any], Path | None]:
    manifest, manifest_path = latest_manifest(base / "out" / "manifests" / "A")
    for step in manifest.get("steps", []):
        if not isinstance(step, dict):
            continue
        haystack = " ".join(
            str(step.get(key, "") or "")
            for key in ("name", "script_or_function", "command", "notes")
        ).lower()
        if "process_stock_receipts_sheet.py" in haystack:
            return step, manifest_path
    return {}, manifest_path


def _b_stock_receipt_token_sync_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    receipts_path = base / "out" / "stock_receipts_latest.csv"
    allocations_path = base / "out" / "token_allocations_live.csv"
    order_master_path = base / "out" / "order_master.csv"
    missing_tokens_path = base / "out" / "orders_missing_tokens.csv"
    preview_summary_path = (
        base
        / "out"
        / "systems"
        / "M"
        / B_STOCK_RECEIPT_SYNC_DIR_NAME
        / B_STOCK_RECEIPT_SYNC_SUMMARY_CSV_NAME
    )

    receipt_rows = read_csv_dicts(receipts_path)
    allocation_rows = read_csv_dicts(allocations_path)
    order_master_rows = read_csv_dicts(order_master_path)
    missing_token_rows = read_csv_dicts(missing_tokens_path)

    schema_errors: list[str] = []
    if not _csv_has_columns(allocations_path, ["order_id", "seller_sku", "token_id"]):
        schema_errors.append("token_allocations_live")
    if not _csv_has_columns(order_master_path, ["Order ID", "SKU"]):
        schema_errors.append("order_master")
    if not _csv_has_columns(missing_tokens_path, ["Order ID", "SKU"]):
        schema_errors.append("orders_missing_tokens")
    if receipt_rows is not None and not _csv_has_columns(receipts_path, ["row_num", "seller_sku", "qty", "order_key"]):
        schema_errors.append("stock_receipts_latest")

    allocated_pairs: set[tuple[str, str]] = set()
    for row in allocation_rows or []:
        order_id = _csv_value(row, ["order_id", "Order ID", "amazon_order_id"])
        sku = _csv_value(row, ["seller_sku", "SKU"])
        token_id = _csv_value(row, ["token_id"])
        if order_id and sku and token_id:
            allocated_pairs.add((order_id, sku))

    missing_pairs: set[tuple[str, str]] = set()
    for row in missing_token_rows or []:
        order_id = _csv_value(row, ["Order ID", "order_id", "amazon_order_id"])
        sku = _csv_value(row, ["SKU", "seller_sku"])
        if order_id and sku:
            missing_pairs.add((order_id, sku))

    placeholder_pairs: set[tuple[str, str]] = set()
    for row in order_master_rows or []:
        order_id = _csv_value(row, ["Order ID", "order_id", "amazon_order_id"])
        sku = _csv_value(row, ["SKU", "seller_sku"])
        missing_flag = _csv_value(row, ["Missing_Token_Flag"])
        placeholder_flag = _csv_value(row, ["COGS_Placeholder_Applied"])
        if order_id and sku and (missing_flag == "1" or placeholder_flag == "1"):
            placeholder_pairs.add((order_id, sku))

    allocated_missing_pairs = sorted(allocated_pairs & missing_pairs)
    allocated_placeholder_pairs = sorted(allocated_pairs & placeholder_pairs)

    receipt_age = file_age_hours(receipts_path, now)
    receipt_count = csv_row_count(receipts_path)
    latest_receipt_row = ""
    if receipt_rows:
        row_nums: list[int] = []
        for row in receipt_rows:
            try:
                row_nums.append(int(float(_csv_value(row, ["row_num"]))))
            except ValueError:
                continue
        if row_nums:
            latest_receipt_row = str(max(row_nums))

    receipt_step, a_manifest_path = _b_latest_a_receipt_step(base)
    receipt_step_status = str(receipt_step.get("step_status", "") or receipt_step.get("status", "") or "").strip().lower()
    receipt_step_notes = str(receipt_step.get("notes", "") or receipt_step.get("verification_status", "") or "").strip()
    receipt_step_text = f"{receipt_step_status} {receipt_step_notes}".lower()
    receipt_intake_disabled = (
        receipt_step_status == "skipped"
        or "a_enable_stock_receipts_sheet=0" in receipt_step_text
    )
    receipt_intake_stale = receipt_age is None or receipt_age >= 24.0
    preview_age = file_age_hours(preview_summary_path, now)
    preview_metrics = {row.get("metric", ""): row.get("value", "") for row in read_csv_rows(preview_summary_path)}
    protected_decision_rows = _mot_int(preview_metrics.get("protected_decision_rows", "0"))
    preview_rows = _mot_int(preview_metrics.get("preview_rows", "0"))
    orders_shipment_rows = _mot_int(preview_metrics.get("orders_shipment_rows", "0"))
    orders_shipment_local_gap_rows = _mot_int(preview_metrics.get("orders_shipment_local_gap_rows", "0"))
    local_orders_file_stale = _mot_int(preview_metrics.get("local_orders_file_stale", "0"))
    orders_staged_refresh_rows = _mot_int(preview_metrics.get("orders_staged_refresh_rows", "0"))
    token_creator_proof_gap_if_unprocessed = _mot_int(
        preview_metrics.get("token_creator_proof_gap_if_unprocessed_total", "0")
    )
    preview_proves_no_waiting_receipts = (
        bool(preview_metrics)
        and str(preview_metrics.get("status", "")).strip().lower() == "ok"
        and preview_rows == 0
        and protected_decision_rows == 0
        and orders_shipment_local_gap_rows == 0
        and local_orders_file_stale == 0
    )

    status = "ok"
    value = "in_sync"
    root_cause = ""
    manager_action = "No action; current B token allocation and order proof agree from the outside."
    luke_action_required = "0"

    if schema_errors:
        status = "fail"
        value = "schema_missing"
        root_cause = "B cannot prove receipt/token sync because one or more proof files are missing required columns."
        manager_action = (
            "Create a bounded manager proof task to repair the proof mapping. "
            "Do not run B, write Sheets, create tokens, edit orders, align the DB, or delete outputs from MOT."
        )
    else:
        warning_parts: list[str] = []
        if receipt_intake_disabled and receipt_intake_stale and not preview_proves_no_waiting_receipts:
            warning_parts.append("receipt_intake_skipped_or_stale")
        if allocated_missing_pairs:
            warning_parts.append(f"allocated_missing_token_rows={len(allocated_missing_pairs)}")
        if allocated_placeholder_pairs:
            warning_parts.append(f"allocated_order_master_placeholder_rows={len(allocated_placeholder_pairs)}")
        if warning_parts:
            status = "warn"
            value = ";".join(warning_parts)
            root_cause = (
                "B has a receipt/token proof gap: either receipt intake is not current, "
                "or a later token allocation has not yet cleared the missing-token/order-master evidence."
            )
            manager_action = (
                "Create or continue a bounded B receipt/token proof task. "
                "If a Sheet receipt row needs a new order key or a correction, stop for Luke because that changes stock facts. "
                "If this is only allocation/order-master timing, retest after the next normal B boundary proof."
            )

    if status != "fail" and preview_rows and protected_decision_rows:
        status = "warn"
        value_parts = []
        value_parts.append(
            f"receipt_rows_need_token_creator_proof;preview_rows={preview_rows};"
            f"protected_live_action_rows={protected_decision_rows};"
            f"token_creator_proof_gap_if_unprocessed={token_creator_proof_gap_if_unprocessed}"
        )
        value = ";".join(value_parts)
        root_cause = (
            "Read-only receipt preview found receipt rows that are not yet proved "
            "in the normal token creator outputs."
        )
        manager_action = (
            "Create or continue a bounded B task to prove the existing token creator path. "
            "Stop for Luke only before Sheet writes, token creation, stock correction, or live cycle action."
        )

    actual_proof = (
        f"receipt_rows={'' if receipt_count is None else receipt_count};"
        f"latest_receipt_row={latest_receipt_row};"
        f"receipt_age_hours={_age_text(receipt_age)};"
        f"a_receipt_step={receipt_step_status or 'not_seen'};"
        f"missing_token_rows={len(missing_pairs)};"
        f"allocated_missing_token_rows={len(allocated_missing_pairs)};"
        f"allocated_order_master_placeholder_rows={len(allocated_placeholder_pairs)}"
    )
    if preview_metrics:
        actual_proof = (
            f"{actual_proof};receipt_preview_rows={preview_rows};"
            f"receipt_preview_protected_decision_rows={protected_decision_rows};"
            f"receipt_preview_token_creator_proof_gap_if_unprocessed={token_creator_proof_gap_if_unprocessed};"
            f"orders_shipment_rows={orders_shipment_rows};"
            f"orders_shipment_local_gap_rows={orders_shipment_local_gap_rows};"
            f"orders_staged_refresh_rows={orders_staged_refresh_rows};"
            f"local_orders_file_age_hours={preview_metrics.get('local_orders_file_age_hours', '')};"
            f"local_orders_file_stale={local_orders_file_stale};"
            f"receipt_preview_age_hours={_age_text(preview_age)};"
            f"receipt_preview_status={preview_metrics.get('status', '')}"
        )
    if receipt_step_notes:
        actual_proof = f"{actual_proof};a_receipt_notes={receipt_step_notes[:120]}"

    source_paths = [receipts_path, allocations_path, order_master_path, missing_tokens_path]
    if a_manifest_path:
        source_paths.append(a_manifest_path)
    if preview_summary_path.exists():
        source_paths.append(preview_summary_path)

    rows = [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_stock_receipt_token_sync",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B007_allocate_tokens_live.py / B004_build_order_master.py / process_stock_receipts_sheet.py",
            expected_output="receipt intake, token allocations, missing-token proof, and Order Master agree",
            actual_proof=actual_proof,
            age_hours=_age_text(receipt_age),
            row_count="" if receipt_count is None else str(receipt_count),
            source_path=";".join(str(path) for path in source_paths),
            summary="B should prove stock receipts, token allocations, missing-token proof, and Order Master agree from the outside.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            luke_action_required=luke_action_required,
            safe_repair_boundary=(
                "B/A receipt-token proof only; no B run or restart, no Sheet write, no token or stock correction, "
                "no order edit, no local DB alignment, no output deletion, no price or queue change."
            ),
        )
    ]
    if preview_metrics:
        shipment_status = "warn" if orders_shipment_local_gap_rows else "ok"
        shipment_value = (
            f"orders_shipment_local_proof_gap={orders_shipment_local_gap_rows};"
            f"orders_shipment_rows={orders_shipment_rows};"
            f"local_orders_file_stale={local_orders_file_stale}"
            if orders_shipment_local_gap_rows
            else "shipment_rows_match_local_proof"
        )
        shipment_root_cause = (
            "The live Google Orders shipment view has rows that do not match the stale local Orders proof file."
            if orders_shipment_local_gap_rows
            else ""
        )
        shipment_manager_action = (
            "Create a separate bounded proof task to refresh the local Orders shipment proof. "
            "Do not create tokens or change stock from this MOT row."
            if orders_shipment_local_gap_rows
            else "No action; shipment rows match local proof."
        )
        rows.append(
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_orders_shipment_local_proof",
                status=shipment_status,
                severity=_severity(shipment_status),
                value=shipment_value,
                producer="SellerOne Orders Google Sheet / b_stock_receipt_intake_preview",
                expected_output="live Orders shipment rows match the local Orders proof file used by stock/token reporting",
                actual_proof=(
                    f"orders_shipment_rows={orders_shipment_rows};"
                    f"orders_shipment_local_gap_rows={orders_shipment_local_gap_rows};"
                    f"orders_staged_refresh_rows={orders_staged_refresh_rows};"
                    f"local_orders_file_age_hours={preview_metrics.get('local_orders_file_age_hours', '')};"
                    f"local_orders_file_stale={local_orders_file_stale}"
                ),
                age_hours=_age_text(preview_age),
                row_count=str(orders_shipment_rows),
                source_path=str(preview_summary_path),
                summary="B should prove the local Orders shipment proof is current without treating it as token creation proof.",
                root_cause_guess=shipment_root_cause,
                manager_action=shipment_manager_action,
                luke_action_required="0",
                safe_repair_boundary=(
                    "B Orders shipment proof only; no B run or restart, no Sheet write, no token or stock correction, "
                    "no order edit, no local DB alignment, no output deletion, no price or queue change."
                ),
            )
        )
    return rows


def _b_protected_token_shortage_summary(path: Path) -> str:
    shortage_rows: list[str] = []
    for row in read_csv_rows(path):
        shortage_class = str(row.get("shortage_class", "") or "").strip().lower()
        next_action = str(row.get("next_action", "") or "").strip().lower()
        is_protected_shortage = (
            shortage_class == "true_live_shortage"
            or shortage_class == "runtime_adjustment_pending"
            or "approved_stock_correction" in next_action
            or "wait_for_receipt" in next_action
            or "rerun_b009" in next_action
        )
        if not is_protected_shortage:
            continue
        sku = str(row.get("seller_sku", "") or row.get("sku", "") or "unknown_sku").strip()
        missing_qty = str(row.get("missing_qty", "") or "").strip()
        shortage_rows.append(f"sku={sku},missing_qty={missing_qty or 'unknown'}")
    if not shortage_rows:
        return ""
    shown = shortage_rows[:3]
    suffix = f",more={len(shortage_rows) - len(shown)}" if len(shortage_rows) > len(shown) else ""
    return "|".join(shown) + suffix


def _parse_pipe_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for index, token in enumerate(str(text or "").replace("\n", "|").split("|")):
        part = token.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            fields[key.strip()] = value.strip()
        elif index == 0:
            fields["owner_label"] = part
    return fields


def _read_lock_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return _parse_pipe_fields(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return {"_read_error": "1"}


def _pid_alive(pid_text: str) -> bool | None:
    try:
        pid = int(str(pid_text or "").strip())
    except ValueError:
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return None
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        exit_code = wintypes.DWORD()
        try:
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            if not ok:
                return None
            return int(exit_code.value) == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lock_heartbeat_age_seconds(fields: dict[str, str], now: datetime) -> float | None:
    heartbeat = fields.get("heartbeat") or fields.get("utc") or fields.get("ts")
    parsed = parse_utc(heartbeat)
    if parsed is None:
        return None
    return max((now - parsed).total_seconds(), 0.0)


def _b_lock_state(path: Path, now: datetime) -> dict[str, object]:
    fields = _read_lock_fields(path)
    if not fields:
        return {"path": path, "exists": False, "live": False, "fields": {}}
    age_seconds = _lock_heartbeat_age_seconds(fields, now)
    pid_alive = _pid_alive(fields.get("pid", ""))
    live = age_seconds is not None and age_seconds < B_HEARTBEAT_FAIL_SECONDS
    return {
        "path": path,
        "exists": True,
        "live": live,
        "fields": fields,
        "age_seconds": age_seconds,
        "pid_alive": pid_alive,
    }


def _b_ownership_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    worker_paths = [
        base / "out" / "systems" / "B" / "live" / "B_cycle.lock",
        base / "out" / "B_cycle.lock",
    ]
    worker_states = [_b_lock_state(path, now) for path in worker_paths]
    present_workers = [state for state in worker_states if state.get("exists")]
    live_workers = [state for state in present_workers if state.get("live")]
    worker_source = ";".join(str(path) for path in worker_paths)
    if not present_workers:
        worker_status = "fail"
        worker_value = "not_running"
        worker_root = "No B worker lock exists, so B is not independently proven running."
    elif len(live_workers) > 1:
        worker_status = "fail"
        worker_value = "duplicate_owner"
        worker_root = "More than one fresh B worker lock exists."
    elif len(live_workers) == 1:
        state = live_workers[0]
        age = state.get("age_seconds")
        worker_status = "warn" if isinstance(age, float) and age >= B_HEARTBEAT_WARN_SECONDS else "ok"
        worker_value = "single_owner"
        worker_root = "B worker heartbeat is getting old." if worker_status == "warn" else ""
    else:
        worker_status = "fail"
        worker_value = "stale_or_dead_owner"
        worker_root = "B worker lock exists, but heartbeat or process evidence is stale or dead."

    live_state = live_workers[0] if live_workers else (present_workers[0] if present_workers else {})
    live_age = live_state.get("age_seconds") if live_state else None
    live_fields = live_state.get("fields", {}) if isinstance(live_state.get("fields", {}), dict) else {}

    supervisor_path = base / "out" / "systems" / "B" / "live" / "B_supervisor.lock"
    supervisor_state = _b_lock_state(supervisor_path, now)
    supervisor_age = supervisor_state.get("age_seconds")
    supervisor_pid_alive = supervisor_state.get("pid_alive")
    if not supervisor_state.get("exists"):
        supervisor_status = "fail"
        supervisor_value = "missing"
        supervisor_root = "No B supervisor lock exists."
    elif supervisor_age is None or supervisor_age >= B_HEARTBEAT_FAIL_SECONDS:
        supervisor_status = "fail"
        supervisor_value = "stale_or_dead"
        supervisor_root = "B supervisor heartbeat evidence is stale or missing."
    elif isinstance(supervisor_age, float) and supervisor_age >= B_HEARTBEAT_WARN_SECONDS:
        supervisor_status = "warn"
        supervisor_value = "heartbeat_old"
        supervisor_root = "B supervisor heartbeat is getting old."
    else:
        supervisor_status = "ok"
        supervisor_value = "fresh"
        supervisor_root = ""

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_worker_owner",
            status=worker_status,
            severity=_severity(worker_status),
            value=worker_value,
            producer="scripts/cycles/run_B_cycle.py",
            expected_output="exactly one fresh B worker owner",
            actual_proof=(
                f"present={len(present_workers)};live={len(live_workers)};pid={live_fields.get('pid', '')};"
                f"heartbeat_age_seconds={_seconds_text(live_age if isinstance(live_age, float) else None)}"
            ),
            age_hours="" if not isinstance(live_age, float) else _age_text(live_age / 3600.0),
            source_path=worker_source,
            summary="B should have exactly one fresh worker owner when the daytime loop is active.",
            root_cause_guess=worker_root,
            manager_action="If fail, package a B ownership repair. Do not clear locks or restart B from MOT.",
            safe_repair_boundary="B ownership proof only; no lock deletion, restart, or worker run.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_supervisor_owner",
            status=supervisor_status,
            severity=_severity(supervisor_status),
            value=supervisor_value,
            producer="scripts/cycles/run_B_supervisor.py",
            expected_output="fresh B supervisor lock",
            actual_proof=(
                f"exists={1 if supervisor_state.get('exists') else 0};pid_alive={supervisor_pid_alive};"
                f"heartbeat_age_seconds={_seconds_text(supervisor_age if isinstance(supervisor_age, float) else None)}"
            ),
            age_hours="" if not isinstance(supervisor_age, float) else _age_text(supervisor_age / 3600.0),
            source_path=str(supervisor_path),
            summary="B supervisor ownership should be fresh so the manager knows who owns the daytime loop.",
            root_cause_guess=supervisor_root,
            manager_action="If fail, package a B supervisor ownership repair. Do not restart B from MOT.",
            safe_repair_boundary="B supervisor proof only; no restart or lock deletion.",
        ),
    ]


def _b_maintenance_marker_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    locks = base / "out" / "locks"
    requested = locks / "maintenance.requested"
    ready = locks / "maintenance.ready"
    active = locks / "maintenance.active"
    scoped = locks / "b_cycle.maintenance"
    markers = {
        "maintenance.requested": requested.exists(),
        "maintenance.ready": ready.exists(),
        "maintenance.active": active.exists(),
        "b_cycle.maintenance": scoped.exists(),
    }
    if markers["maintenance.active"] and _read_lock_fields(base / "out" / "systems" / "B" / "live" / "B_cycle.lock"):
        status = "fail"
        value = "active_marker_while_b_owner_present"
        root_cause = "Maintenance active marker and B worker ownership are both visible."
    elif markers["b_cycle.maintenance"]:
        status = "warn"
        value = "b_scoped_maintenance_present"
        root_cause = "A B-scoped maintenance marker is present."
    elif markers["maintenance.requested"] and not markers["maintenance.ready"]:
        status = "warn"
        value = "handoff_requested_not_ready"
        root_cause = "A maintenance request exists but B has not marked ready."
    elif markers["maintenance.ready"] and not markers["maintenance.requested"] and not markers["maintenance.active"]:
        status = "warn"
        value = "orphan_ready_marker"
        root_cause = "A maintenance.ready marker exists without an active request."
    else:
        status = "ok"
        value = "clear_or_consistent"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_maintenance_marker_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B/A maintenance handoff",
            expected_output="safe B maintenance marker state",
            actual_proof=";".join(f"{name}={1 if exists else 0}" for name, exists in markers.items()),
            source_path=";".join(str(path) for path in [requested, ready, active, scoped]),
            summary="B maintenance markers should prove safe handoff state without requiring the manager to touch locks.",
            root_cause_guess=root_cause,
            manager_action="If fail, stop and package ownership proof. Do not create, clear, or edit maintenance markers from MOT.",
            safe_repair_boundary="B maintenance proof only; no marker edits, restart, or worker run.",
        )
    ]


def _b_refund_pnl_bridge_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    bridge_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv"
    rate_path = base / "out" / "systems" / "B" / "refunds" / "b_sku_refund_rate.csv"
    bridge_rows = read_csv_rows(bridge_path)
    rate_rows = read_csv_rows(rate_path)
    bridge_headers = csv_headers(bridge_path) or []
    rate_headers = csv_headers(rate_path) or []
    bridge_required = {
        "order_id",
        "sku",
        "refund_posted_date",
        "refund_units",
        "refund_profit_impact_exvat",
        "sellerboard_match_state",
        "api_refund_proof_state",
        "pnl_inclusion_state",
    }
    rate_required = {
        "sku",
        "window_days",
        "sales_units",
        "refund_units",
        "refund_unit_rate",
        "expected_refund_cost_per_unit_gbp",
        "basis",
        "sample_confidence",
        "proof_state",
    }
    missing_files = [str(path) for path in [bridge_path, rate_path] if not path.exists()]
    missing_schema = [
        *(f"bridge:{col}" for col in sorted(bridge_required - set(bridge_headers))),
        *(f"rate:{col}" for col in sorted(rate_required - set(rate_headers))),
    ]
    api_rows = [row for row in bridge_rows if _mot_text(row.get("api_refund_proof_state", "")) == "api_proved"]
    bridge_only_rows = [
        row for row in bridge_rows if _mot_text(row.get("api_refund_proof_state", "")) == "sellerboard_bridge_only"
    ]
    bad_api_rows = [
        row
        for row in api_rows
        if not _mot_text(row.get("order_id", ""))
        or not _mot_text(row.get("sku", ""))
        or not _mot_text(row.get("refund_posted_date", ""))
        or _o_num(row.get("refund_units", "")) is None
    ]
    rate_api_rows = [
        row
        for row in rate_rows
        if _mot_text(row.get("proof_state", "")) in {"api_proved", "api_proved_or_not_applicable"}
    ]
    if len(missing_files) == 2:
        status = "not_checked"
        value = "waiting_for_refund_proof_builder"
        root = "B refund proof waits until the B037 refund bridge has run."
    elif missing_files or missing_schema or bad_api_rows:
        status = "fail"
        value = "missing_or_invalid_refund_proof"
        root = "B refund proof files are missing, have schema gaps, or contain API refund rows without required proof fields."
    elif bridge_only_rows:
        status = "warn"
        value = f"api_refunds={len(api_rows)};sellerboard_bridge_only={len(bridge_only_rows)};rate_rows={len(rate_rows)}"
        root = "Sellerboard return evidence still exists without matching API refund proof."
    elif not bridge_rows or not rate_rows:
        status = "warn"
        value = f"api_refunds={len(api_rows)};rate_rows={len(rate_rows)}"
        root = "B refund proof has not yet produced both bridge and SKU refund-rate rows."
    else:
        status = "ok"
        value = f"api_refunds={len(api_rows)};sellerboard_bridge_only=0;rate_rows={len(rate_rows)}"
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_refund_pnl_roi_api_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B037_build_refund_pnl_bridge.py",
            expected_output="API refund bridge and SKU refund-rate proof",
            actual_proof=(
                f"bridge_exists={1 if bridge_path.exists() else 0};"
                f"rate_exists={1 if rate_path.exists() else 0};"
                f"bridge_rows={len(bridge_rows)};"
                f"api_refund_rows={len(api_rows)};"
                f"sellerboard_bridge_only_rows={len(bridge_only_rows)};"
                f"bad_api_rows={len(bad_api_rows)};"
                f"rate_rows={len(rate_rows)};"
                f"api_rate_rows={len(rate_api_rows)};"
                f"missing_schema={';'.join(missing_schema[:20])};"
                f"missing_files={';'.join(missing_files)}"
            ),
            row_count=str(len(bridge_rows)),
            source_path=f"{bridge_path};{rate_path}",
            summary="B refunds should be traceable from API refund rows into P&L and SKU refund-rate proof without using Sellerboard as final money truth.",
            root_cause_guess=root,
            manager_action=(
                "Repair the refund proof builder or wait for API refund evidence. "
                "Do not use Sellerboard estimates as live ROI or restocking truth."
            ),
            safe_repair_boundary="B refund proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or Sellerboard-as-final-ROI use.",
        )
    ]


def _b_refund_return_token_bridge_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    bridge_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_summary.csv"
    rows = read_csv_rows(bridge_path)
    headers = csv_headers(bridge_path) or []
    required = {
        "order_id",
        "sku",
        "api_refund_proof_state",
        "amazon_return_proof_state",
        "token_return_state",
        "return_cogs_recovered_exvat",
        "blocked_return_cogs_exvat",
        "sellerboard_match_state",
        "proof_label",
        "roi_stock_recovery_state",
        "mismatch_state",
    }
    missing_schema = sorted(required - set(headers))
    label_counts: dict[str, int] = {}
    for row in rows:
        label = _mot_text(row.get("proof_label", "")) or "blank"
        label_counts[label] = label_counts.get(label, 0) + 1
    warning_rows = [row for row in rows if _mot_text(row.get("mismatch_state", "")) == "warning"]
    sellable_missing = label_counts.get("returned_sellable_token_missing", 0)
    token_reuse_without_amazon = label_counts.get("token_reuse_without_amazon_return_proof", 0)
    sellerboard_only = label_counts.get("sellerboard_witness_only", 0)
    sellable_reused = label_counts.get("returned_sellable_token_reused", 0)
    blocked_cogs_rows = [
        row
        for row in rows
        if _o_num(row.get("blocked_return_cogs_exvat", "")) is not None
        and float(_o_num(row.get("blocked_return_cogs_exvat", "")) or 0.0) > 0
    ]
    if not bridge_path.exists():
        status = "not_checked"
        value = "waiting_for_return_token_bridge"
        root = "B return-token proof bridge has not been built yet."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_return_token_bridge_schema"
        root = "B return-token proof bridge is missing required proof columns."
    elif warning_rows:
        status = "warn"
        value = (
            f"rows={len(rows)};warnings={len(warning_rows)};"
            f"sellable_missing={sellable_missing};"
            f"token_reuse_without_amazon={token_reuse_without_amazon};"
            f"sellerboard_only={sellerboard_only};"
            f"sellable_reused={sellable_reused};"
            f"blocked_return_cogs={len(blocked_cogs_rows)}"
        )
        root = "Refund money, Amazon return proof, and token-return proof do not fully agree yet."
    else:
        status = "ok"
        value = f"rows={len(rows)};warnings=0;sellable_reused={sellable_reused};blocked_return_cogs={len(blocked_cogs_rows)}"
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_refund_return_token_bridge",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B038_build_refund_return_token_bridge.py",
            expected_output="Refund return token proof bridge with proof labels and mismatch counts",
            actual_proof=(
                f"bridge_exists={1 if bridge_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"rows={len(rows)};"
                f"warning_rows={len(warning_rows)};"
                f"returned_sellable_token_missing={sellable_missing};"
                f"token_reuse_without_amazon_return_proof={token_reuse_without_amazon};"
                f"sellerboard_witness_only={sellerboard_only};"
                f"returned_sellable_token_reused={sellable_reused};"
                f"blocked_return_cogs_rows={len(blocked_cogs_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(rows)),
            source_path=f"{bridge_path};{summary_path}",
            summary="B refund stock recovery must agree across API refund money, Amazon return proof, and the existing token-return chain.",
            root_cause_guess=root,
            manager_action=(
                "Build or repair the read-only return-token bridge. Do not create tokens, run B, "
                "write Sheets, align the DB, or let unproved stock recovery affect ROI/restocking."
            ),
            safe_repair_boundary=(
                "B refund return-token proof only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_return_cogs_residual_review_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "B" / "refunds" / "b_return_cogs_residual_review.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_return_cogs_residual_review_summary.csv"
    review_rows = read_csv_rows(review_path)
    headers = csv_headers(review_path) or []
    required = {
        "order_id",
        "sku",
        "amazon_return_disposition",
        "recovered_cogs_allowed_exvat",
        "blocked_return_cogs_exvat",
        "residual_review_state",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
    }
    missing_schema = sorted(required - set(headers))
    unsafe_rows = [
        row
        for row in review_rows
        if _mot_text(row.get("residual_review_state", "")) == "unsafe_non_sellable_cogs_recovery"
        or _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}
    ]
    blocked_rows = [
        row
        for row in review_rows
        if _o_num(row.get("blocked_return_cogs_exvat", "")) is not None
        and float(_o_num(row.get("blocked_return_cogs_exvat", "")) or 0.0) > 0
    ]
    if not review_path.exists():
        status = "not_checked"
        value = "waiting_for_return_cogs_residual_review"
        root = "B return COGS residual safety review has not been built yet."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_return_cogs_residual_review_schema"
        root = "B return COGS residual review is missing required manager safety columns."
    elif unsafe_rows:
        status = "fail"
        value = f"review_rows={len(review_rows)};unsafe_rows={len(unsafe_rows)};blocked_rows={len(blocked_rows)}"
        root = "Some non-sellable return COGS evidence still appears allowed into stock recovery, ROI, or Sellerboard-final truth."
    else:
        status = "ok"
        value = f"review_rows={len(review_rows)};blocked_rows={len(blocked_rows)};unsafe_rows=0"
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_return_cogs_residual_review",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B064_build_return_cogs_residual_review.py",
            expected_output="Read-only proof that non-sellable return COGS residuals are blocked from stock recovery and ROI",
            actual_proof=(
                f"review_exists={1 if review_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"review_rows={len(review_rows)};"
                f"blocked_rows={len(blocked_rows)};"
                f"unsafe_rows={len(unsafe_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(review_rows)),
            source_path=f"{review_path};{summary_path}",
            summary="B should keep non-sellable return COGS history visible while blocking it from recovered-stock, ROI, and restocking truth.",
            root_cause_guess=root,
            manager_action=(
                "If fail, repair the B refund-return proof mapping. Do not edit token return ledger rows, run B, "
                "write Sheets, align DB facts, or let blocked COGS affect ROI/restocking."
            ),
            safe_repair_boundary=(
                "B return COGS residual proof only; no token ledger correction, B run, Sheet write, local DB alignment, "
                "output deletion, price change, queue edit, Sellerboard-final truth, or live ROI/restocking use."
            ),
        )
    ]


def _b_return_token_matching_audit_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    audit_path = base / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit_summary.csv"
    audit_rows = read_csv_rows(audit_path)
    headers = csv_headers(audit_path) or []
    required = {
        "order_id",
        "sku",
        "proof_label",
        "diagnosis",
        "future_proofing_need",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in audit_rows
        if not _mot_text(row.get("diagnosis", ""))
        or _mot_text(row.get("diagnosis", "")).lower() == "warning needs manual proof classification."
    ]
    b008_missing = [
        row
        for row in audit_rows
        if _o_num(row.get("b008_applied_qty", "")) is not None and float(_o_num(row.get("b008_applied_qty", "")) or 0.0) <= 0
    ]
    sellable_missing = [
        row for row in audit_rows if _mot_text(row.get("proof_label", "")) == "returned_sellable_token_missing"
    ]
    token_reuse_without_amazon = [
        row for row in audit_rows if _mot_text(row.get("proof_label", "")) == "token_reuse_without_amazon_return_proof"
    ]
    non_sellable_reuse = [
        row
        for row in audit_rows
        if _mot_text(row.get("amazon_return_disposition", "")).upper() != "SELLABLE"
        and _mot_text(row.get("token_return_state", "")) == "reusable_return_token_seen"
    ]
    if not audit_path.exists():
        status = "not_checked"
        value = "waiting_for_return_token_matching_audit"
        root = "B return-token warnings have not yet been classified into worker-ready causes."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_return_token_matching_audit_schema"
        root = "B return-token matching audit is missing required columns."
    elif unclassified_rows:
        status = "warn"
        value = f"audit_rows={len(audit_rows)};unclassified={len(unclassified_rows)}"
        root = "Some B return-token warning rows still need a clearer diagnosis before repair."
    else:
        status = "ok"
        value = (
            f"audit_rows={len(audit_rows)};"
            f"b008_missing={len(b008_missing)};"
            f"sellable_missing={len(sellable_missing)};"
            f"token_reuse_without_amazon={len(token_reuse_without_amazon)};"
            f"non_sellable_reuse={len(non_sellable_reuse)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_return_token_matching_audit",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B040_audit_refund_return_token_matching.py",
            expected_output="Worker-ready diagnosis of B refund return-token warning rows",
            actual_proof=(
                f"audit_exists={1 if audit_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"audit_rows={len(audit_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"b008_missing_or_zero_applied={len(b008_missing)};"
                f"sellable_missing={len(sellable_missing)};"
                f"token_reuse_without_amazon={len(token_reuse_without_amazon)};"
                f"non_sellable_reuse={len(non_sellable_reuse)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(audit_rows)),
            source_path=f"{audit_path};{summary_path}",
            summary="B return-token warning rows should be classified into B008, B009, Amazon-report coverage, or bridge-proof repair causes.",
            root_cause_guess=root,
            manager_action="Use the audit to create bounded worker packets. Do not hand-edit tokens or feed unproved stock recovery into ROI.",
            safe_repair_boundary=(
                "B return-token matching audit only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_return_token_repair_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "proof_label",
        "diagnosis",
        "repair_lane",
        "repair_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "sellerboard_final_truth_allowed",
        "roi_or_restock_use_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("repair_lane", ""))
        or not _mot_text(row.get("repair_readiness", ""))
        or not _mot_text(row.get("preview_action", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    b008_rows = [row for row in preview_rows if _mot_text(row.get("repair_lane", "")) == "b008_refund_token_marking"]
    b009_rows = [row for row in preview_rows if _mot_text(row.get("repair_lane", "")) == "b009_order_aware_sellable_return"]
    cogs_rows = [row for row in preview_rows if _mot_text(row.get("repair_lane", "")) == "return_cogs_trace"]
    amazon_rows = [row for row in preview_rows if _mot_text(row.get("repair_lane", "")) == "amazon_return_coverage_review"]
    conflict_rows = [row for row in preview_rows if _mot_text(row.get("repair_lane", "")) == "protected_disposition_conflict"]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_return_token_repair_preview"
        root = "B return-token warnings have not yet been turned into safe repair-preview lanes."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_return_token_repair_preview_schema"
        root = "B return-token repair preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The preview is unsafe because it appears to allow a live write, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified={len(unclassified_rows)}"
        root = "Some B return-token warning rows still do not have a concrete repair lane."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"b008={len(b008_rows)};"
            f"b009={len(b009_rows)};"
            f"cogs={len(cogs_rows)};"
            f"amazon_coverage={len(amazon_rows)};"
            f"protected_conflicts={len(conflict_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_return_token_repair_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B041_build_return_token_repair_preview.py",
            expected_output="Read-only B return-token repair preview with no live write, no ROI use, and no Sellerboard-as-final truth",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"b008_reproof_rows={len(b008_rows)};"
                f"b009_order_aware_rows={len(b009_rows)};"
                f"return_cogs_trace_rows={len(cogs_rows)};"
                f"amazon_coverage_review_rows={len(amazon_rows)};"
                f"protected_conflict_rows={len(conflict_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="B return-token warnings should become safe repair-preview lanes before any protected live token repair is proposed.",
            root_cause_guess=root,
            manager_action=(
                "Use this preview to create bounded B008/B009 worker packets. "
                "Do not hand-edit tokens or feed unproved stock recovery into ROI."
            ),
            safe_repair_boundary=(
                "B return-token repair preview only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_refund_return_warning_workpack_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    workpack_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack_summary.csv"
    workpack_rows = read_csv_rows(workpack_path)
    headers = csv_headers(workpack_path) or []
    required = {
        "repair_lane",
        "repair_readiness",
        "row_count",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "luke_decision_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "manager_state",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in workpack_rows
        if not _mot_text(row.get("repair_lane", ""))
        or not _mot_text(row.get("manager_expectation", ""))
        or not _mot_text(row.get("bounded_worker_task", ""))
        or _mot_text(row.get("manager_state", "")) == "unclassified_needs_manager_mapping"
    ]
    live_write_rows = [
        row for row in workpack_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}
    ]
    roi_rows = [row for row in workpack_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [
        row for row in workpack_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}
    ]
    protected_rows = 0
    total_preview_rows = 0
    for row in workpack_rows:
        try:
            protected_rows += int(float(_mot_text(row.get("protected_before_apply", "")) or "0"))
        except Exception:
            pass
        try:
            total_preview_rows += int(float(_mot_text(row.get("row_count", "")) or "0"))
        except Exception:
            pass
    if not workpack_path.exists():
        status = "not_checked"
        value = "waiting_for_refund_return_warning_workpack"
        root = "B return-token warning rows have not yet been grouped into manager-owned workpack lanes."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_refund_return_warning_workpack_schema"
        root = "B refund-return warning workpack is missing required manager safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_lanes={len(live_write_rows)};"
            f"roi_lanes={len(roi_rows)};"
            f"sellerboard_lanes={len(sellerboard_rows)}"
        )
        root = "The warning workpack is unsafe because a lane allows live write, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"workpack_lanes={len(workpack_rows)};unclassified_lanes={len(unclassified_rows)}"
        root = "Some refund-return warning lanes are not manager-classified."
    else:
        status = "ok"
        value = (
            f"warning_rows={total_preview_rows};"
            f"workpack_lanes={len(workpack_rows)};"
            f"protected_rows={protected_rows};"
            f"unclassified_lanes=0"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_refund_return_warning_workpack",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B051_build_refund_return_warning_workpack.py",
            expected_output="Manager-owned workpack grouping refund-return token warnings into bounded repair lanes",
            actual_proof=(
                f"workpack_exists={1 if workpack_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"warning_rows={total_preview_rows};"
                f"workpack_lanes={len(workpack_rows)};"
                f"protected_rows={protected_rows};"
                f"unclassified_lanes={len(unclassified_rows)};"
                f"live_write_lanes={len(live_write_rows)};"
                f"roi_lanes={len(roi_rows)};"
                f"sellerboard_final_truth_lanes={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(workpack_rows)),
            source_path=f"{workpack_path};{summary_path}",
            summary="B refund-return warnings should be grouped into manager-owned lanes before protected repair work is proposed.",
            root_cause_guess=root,
            manager_action=(
                "Use the workpack to create bounded B worker packets. Keep bridge warnings visible and keep ROI/restocking "
                "blocked from unproved stock recovery."
            ),
            safe_repair_boundary=(
                "B refund-return warning workpack only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_fallback_token_cost_audit_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    audit_path = base / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv"
    audit_rows = read_csv_rows(audit_path)
    summary_rows = read_csv_rows(summary_path)
    metric_rows = {row.get("metric", ""): row for row in summary_rows}
    headers = csv_headers(audit_path) or []
    required = {
        "token_id",
        "seller_sku",
        "cost_per_unit",
        "cost_proof_state",
        "manager_label",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "protected_before_apply",
    }
    missing_schema = sorted(required - set(headers))
    weak_rows = [
        row
        for row in audit_rows
        if _mot_text(row.get("manager_label", "")) in {"weak_fallback_cost", "not_yet_proven"}
        or _mot_text(row.get("cost_proof_state", "")) in {"fallback_cost_weak_latest_token", "fallback_cost_unproved"}
    ]
    unsafe_rows = [
        row
        for row in audit_rows
        if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}
    ]
    fallback_rows = _summary_metric_int(metric_rows, "fallback_token_rows")
    receipt_proved = _summary_metric_int(metric_rows, "receipt_proved_rows")
    source_proved = _summary_metric_int(metric_rows, "source_token_proved_rows")
    weak_or_unproved = _summary_metric_int(metric_rows, "weak_or_unproved_rows") or len(weak_rows)

    if not audit_path.exists():
        status = "not_checked"
        value = "waiting_for_fallback_token_cost_audit"
        root = "B fallback returned-stock token costs have not yet been independently audited."
        action = "Build the read-only B fallback cost audit before treating fallback token costs as proved."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_fallback_token_cost_audit_schema"
        root = "B fallback cost audit is missing required manager proof columns."
        action = "Repair the read-only audit shape. Do not edit tokens, run B, write Sheets, align DB facts, or use the values in ROI/restocking."
    elif unsafe_rows:
        status = "fail"
        value = f"fallback_tokens={fallback_rows or len(audit_rows)};unsafe_live_use_rows={len(unsafe_rows)}"
        root = "The fallback cost audit has unsafe live-use flags enabled."
        action = "Turn off live-use flags in the proof output. A cost audit may prove source evidence, but it must not approve live ROI/restocking."
    elif weak_rows or weak_or_unproved:
        status = "warn"
        value = (
            f"fallback_tokens={fallback_rows or len(audit_rows)};"
            f"weak_or_unproved={weak_or_unproved};"
            f"receipt_proved={receipt_proved};source_token_proved={source_proved}"
        )
        root = "Some fallback returned-stock token costs are still weakly proved or not yet proved."
        action = (
            "Keep weak fallback costs warning-labelled and prepare a read-only correction preview if needed. "
            "Do not correct old token data or let weak costs affect ROI/restocking without Luke."
        )
    else:
        status = "ok"
        value = (
            f"fallback_tokens={fallback_rows or len(audit_rows)};"
            f"weak_or_unproved=0;"
            f"receipt_proved={receipt_proved};source_token_proved={source_proved}"
        )
        root = ""
        action = "Keep the audit under MOT. Future fallback tokens still need receipt or source-token proof before creation."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_fallback_token_cost_audit",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B070_build_fallback_token_cost_audit.py",
            expected_output="Read-only audit proving where fallback returned-stock token costs came from",
            actual_proof=(
                f"audit_exists={1 if audit_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"audit_rows={len(audit_rows)};"
                f"fallback_token_rows={fallback_rows};"
                f"receipt_proved={receipt_proved};"
                f"source_token_proved={source_proved};"
                f"weak_or_unproved={weak_or_unproved};"
                f"unsafe_live_use_rows={len(unsafe_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(audit_rows)),
            source_path=f"{audit_path};{summary_path}",
            summary="B fallback returned-stock token costs must show receipt/source proof or remain warning-labelled before ROI/restocking trust them.",
            root_cause_guess=root,
            manager_action=action,
            safe_repair_boundary=(
                "Read-only B fallback cost proof only; no B run, restart, token correction, stock correction, "
                "Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_fallback_cost_proof_reconciliation_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    recon_path = base / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation_summary.csv"
    recon_rows = read_csv_rows(recon_path)
    summary_rows = read_csv_rows(summary_path)
    metric_rows = {row.get("metric", ""): row for row in summary_rows}
    headers = csv_headers(recon_path) or []
    required = {
        "token_id",
        "seller_sku",
        "b070_cost_proof_state",
        "sheet_issue",
        "reconciliation_rule",
        "clean_h_o_trust_allowed",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "protected_before_apply",
    }
    missing_schema = sorted(required - set(headers))
    allowed_rules = {"sheet_cost_supersedes_source_token", "source_token_cost_is_valid", "requires_batch_link_proof", "requires_luke_business_decision"}
    unclassified = [row for row in recon_rows if _mot_text(row.get("reconciliation_rule", "")) not in allowed_rules]
    unsafe_rows = [
        row
        for row in recon_rows
        if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}
    ]
    requires_rows = [row for row in recon_rows if _mot_text(row.get("reconciliation_rule", "")) == "requires_batch_link_proof"]
    decision_rows = [row for row in recon_rows if _mot_text(row.get("reconciliation_rule", "")) == "requires_luke_business_decision"]
    valid_rows = [row for row in recon_rows if _mot_text(row.get("reconciliation_rule", "")) == "source_token_cost_is_valid"]
    h_blocked = _summary_metric(metric_rows, "h_next_available_blocked_skus") or ""
    if not recon_path.exists():
        status = "not_checked"
        value = "waiting_for_fallback_cost_proof_reconciliation"
        root = "B070 source-cost proof and Sheet cost comparison have not yet been reconciled."
        action = "Build B071 before H/O treat source-token-proved fallback costs as clean business truth."
        luke = "0"
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_fallback_cost_reconciliation_schema"
        root = "B fallback cost reconciliation is missing required manager proof columns."
        action = "Repair the read-only reconciliation shape. Do not edit token data or feed fallback costs into live ROI/restocking."
        luke = "0"
    elif unsafe_rows or unclassified:
        status = "fail"
        value = f"reconciliation_rows={len(recon_rows)};unsafe_rows={len(unsafe_rows)};unclassified_rows={len(unclassified)}"
        root = "B fallback cost reconciliation is unsafe or has unclassified rows."
        action = "Repair the read-only proof labels and live-use flags only."
        luke = "0"
    elif decision_rows:
        status = "decision_needed"
        value = f"reconciliation_rows={len(recon_rows)};decision_rows={len(decision_rows)}"
        root = "A business rule decision is needed before fallback costs can be trusted downstream."
        action = "Stop for Luke before choosing a business rule that lets fallback costs affect ROI/restocking."
        luke = "1"
    elif requires_rows:
        status = "warn"
        value = (
            f"reconciliation_rows={len(recon_rows)};"
            f"requires_batch_link_proof={len(requires_rows)};"
            f"source_token_cost_valid={len(valid_rows)};"
            f"h_blocked_skus={h_blocked}"
        )
        root = "Some source-token-proved fallback costs are traceable but not clean enough for H/O trust because Sheet cost comparison disagrees."
        action = "Keep affected SKUs blocked from clean H/O trust until batch-linked proof or protected correction clears them."
        luke = "0"
    else:
        status = "ok"
        value = f"reconciliation_rows={len(recon_rows)};requires_batch_link_proof=0;source_token_cost_valid={len(valid_rows)}"
        root = ""
        action = "B070 source proof and Sheet comparison agree for clean downstream trust."
        luke = "0"

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_fallback_cost_proof_reconciliation",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B071_build_fallback_cost_proof_reconciliation.py",
            expected_output="Read-only reconciliation between B070 source-token proof and Sheet cost comparison",
            actual_proof=(
                f"reconciliation_exists={1 if recon_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"reconciliation_rows={len(recon_rows)};"
                f"requires_batch_link_proof_rows={len(requires_rows)};"
                f"source_token_cost_valid_rows={len(valid_rows)};"
                f"decision_rows={len(decision_rows)};"
                f"unsafe_rows={len(unsafe_rows)};"
                f"unclassified_rows={len(unclassified)};"
                f"h_next_available_blocked_skus={h_blocked};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(recon_rows)),
            source_path=f"{recon_path};{summary_path}",
            summary="B fallback cost proof must reconcile source-token proof with Sheet cost comparison before H/O treat it as clean trust.",
            root_cause_guess=root,
            manager_action=action,
            luke_action_required=luke,
            safe_repair_boundary=(
                "Read-only B fallback cost reconciliation only; no B run, restart, token correction, stock correction, "
                "Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_amazon_return_coverage_audit_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    audit_path = base / "out" / "systems" / "B" / "refunds" / "b_amazon_return_coverage_audit.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_amazon_return_coverage_audit_summary.csv"
    audit_rows = read_csv_rows(audit_path)
    headers = csv_headers(audit_path) or []
    required = {
        "order_id",
        "sku",
        "repair_lane",
        "exact_customer_return_rows",
        "customer_return_match_state",
        "stock_signal_state",
        "coverage_conclusion",
        "manager_coverage_label",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    }
    missing_schema = sorted(required - set(headers))
    safe_labels = {
        "exact_amazon_return_proved",
        "stock_adjustment_only",
        "token_only",
        "nearby_sku_only",
        "not_yet_proven",
    }
    unclassified_rows = [
        row
        for row in audit_rows
        if not _mot_text(row.get("coverage_conclusion", ""))
        or _mot_text(row.get("manager_coverage_label", "")) not in safe_labels
        or not _mot_text(row.get("manager_expectation", ""))
        or not _mot_text(row.get("bounded_worker_task", ""))
    ]
    live_write_rows = [row for row in audit_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in audit_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in audit_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    exact_rows = [row for row in audit_rows if _mot_text(row.get("manager_coverage_label", "")) == "exact_amazon_return_proved"]
    stock_only_rows = [row for row in audit_rows if _mot_text(row.get("manager_coverage_label", "")) == "stock_adjustment_only"]
    nearby_rows = [row for row in audit_rows if _mot_text(row.get("manager_coverage_label", "")) == "nearby_sku_only"]
    token_only_rows = [row for row in audit_rows if _mot_text(row.get("manager_coverage_label", "")) == "token_only"]
    not_yet_proven_rows = [row for row in audit_rows if _mot_text(row.get("manager_coverage_label", "")) == "not_yet_proven"]
    if not audit_path.exists():
        status = "not_checked"
        value = "waiting_for_amazon_return_coverage_audit"
        root = "The Amazon return coverage lane has not yet been audited."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_amazon_return_coverage_audit_schema"
        root = "The Amazon return coverage audit is missing required manager proof columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The audit is unsafe because it appears to allow live writes, ROI/restocking use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"audit_rows={len(audit_rows)};unclassified_rows={len(unclassified_rows)}"
        root = "Some Amazon return coverage rows are not classified."
    else:
        status = "ok"
        value = (
            f"audit_rows={len(audit_rows)};"
            f"exact_customer_return={len(exact_rows)};"
            f"stock_adjustment_only={len(stock_only_rows)};"
            f"nearby_sku_only={len(nearby_rows)};"
            f"token_only={len(token_only_rows)};"
            f"not_yet_proven={len(not_yet_proven_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_amazon_return_coverage_audit",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B052_build_amazon_return_coverage_audit.py",
            expected_output="Read-only audit separating Amazon customer-return proof from stock-adjustment-only return signals",
            actual_proof=(
                f"audit_exists={1 if audit_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"audit_rows={len(audit_rows)};"
                f"exact_customer_return_rows={len(exact_rows)};"
                f"stock_adjustment_without_customer_return_rows={len(stock_only_rows)};"
                f"manager_stock_adjustment_only_rows={len(stock_only_rows)};"
                f"nearby_sku_only_rows={len(nearby_rows)};"
                f"token_only_rows={len(token_only_rows)};"
                f"not_yet_proven_rows={len(not_yet_proven_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(audit_rows)),
            source_path=f"{audit_path};{summary_path}",
            summary="B Amazon return coverage proof must separate customer-return order proof from stock-adjustment-only evidence before stock recovery affects ROI.",
            root_cause_guess=root,
            manager_action=(
                "Use B052 to create the next bounded B worker packet. Do not create tokens, run B, write Sheets, "
                "align the DB, or let stock-adjustment-only evidence affect ROI/restocking."
            ),
            safe_repair_boundary=(
                "B Amazon return coverage audit only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, Sellerboard-final truth, or live ROI/restocking use."
            ),
        )
    ]


def _b_original_allocation_gap_audit_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    audit_path = base / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit_summary.csv"
    audit_rows = read_csv_rows(audit_path)
    headers = csv_headers(audit_path) or []
    required = {
        "order_id",
        "sku",
        "api_refund_rows",
        "refund_bridge_original_order_state",
        "orders_all_rows",
        "order_items_all_rows",
        "token_allocation_rows",
        "token_ledger_allocated_rows",
        "allocation_gap_conclusion",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in audit_rows
        if not _mot_text(row.get("allocation_gap_conclusion", ""))
        or not _mot_text(row.get("manager_expectation", ""))
        or not _mot_text(row.get("bounded_worker_task", ""))
    ]
    live_write_rows = [row for row in audit_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in audit_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in audit_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    refund_without_original_rows = [
        row
        for row in audit_rows
        if _mot_text(row.get("allocation_gap_conclusion", ""))
        == "refund_money_without_original_order_or_allocation_proof"
    ]
    order_seen_allocation_missing_rows = [
        row for row in audit_rows if _mot_text(row.get("allocation_gap_conclusion", "")) == "order_seen_allocation_missing"
    ]
    allocation_ledger_gap_rows = [
        row
        for row in audit_rows
        if _mot_text(row.get("allocation_gap_conclusion", "")) == "allocation_exists_token_ledger_missing"
    ]
    mapping_gap_rows = [
        row
        for row in audit_rows
        if _mot_text(row.get("allocation_gap_conclusion", "")) == "allocation_proof_exists_bridge_mapping_gap"
    ]
    if not audit_path.exists():
        status = "not_checked"
        value = "waiting_for_original_allocation_gap_audit"
        root = "The original allocation gap lane has not yet been audited."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_original_allocation_gap_audit_schema"
        root = "The original allocation gap audit is missing required manager proof columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The audit is unsafe because it appears to allow live writes, ROI/restocking use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"audit_rows={len(audit_rows)};unclassified_rows={len(unclassified_rows)}"
        root = "Some original allocation gap rows are not classified."
    else:
        status = "ok"
        value = (
            f"audit_rows={len(audit_rows)};"
            f"refund_without_original={len(refund_without_original_rows)};"
            f"order_seen_allocation_missing={len(order_seen_allocation_missing_rows)};"
            f"allocation_ledger_gap={len(allocation_ledger_gap_rows)};"
            f"mapping_gap={len(mapping_gap_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_allocation_gap_audit",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B053_build_original_allocation_gap_audit.py",
            expected_output="Read-only audit proving the earliest missing source for B008 original allocation gaps",
            actual_proof=(
                f"audit_exists={1 if audit_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"audit_rows={len(audit_rows)};"
                f"refund_money_without_original_order_rows={len(refund_without_original_rows)};"
                f"order_seen_allocation_missing_rows={len(order_seen_allocation_missing_rows)};"
                f"allocation_exists_token_ledger_missing_rows={len(allocation_ledger_gap_rows)};"
                f"allocation_proof_exists_bridge_mapping_gap_rows={len(mapping_gap_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(audit_rows)),
            source_path=f"{audit_path};{summary_path}",
            summary="B original allocation proof must identify whether refund rows are missing the original order, order item, allocation, or token-ledger proof.",
            root_cause_guess=root,
            manager_action=(
                "Use B053 to create the next bounded B worker packet. Do not create tokens, run B, write Sheets, "
                "align the DB, or let missing original allocation rows affect stock recovery."
            ),
            safe_repair_boundary=(
                "B original allocation gap audit only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, Sellerboard-final truth, or live ROI/restocking use."
            ),
        )
    ]


def _b_original_order_recovery_proof_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    proof_path = base / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof_summary.csv"
    proof_rows = read_csv_rows(proof_path)
    headers = csv_headers(proof_path) or []
    required = {
        "order_id",
        "sku",
        "api_refund_rows",
        "orders_raw_rows",
        "order_items_raw_rows",
        "orders_all_rows",
        "order_items_all_rows",
        "order_master_rows",
        "level1_rows",
        "token_allocation_rows",
        "quarantine_rows",
        "quarantine_api_proved_rows",
        "quarantine_required_field_gaps",
        "original_order_recovery_state",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in proof_rows
        if not _mot_text(row.get("original_order_recovery_state", ""))
        or not _mot_text(row.get("manager_expectation", ""))
        or not _mot_text(row.get("bounded_worker_task", ""))
    ]
    live_write_rows = [row for row in proof_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in proof_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in proof_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    needs_api_fetch_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("original_order_recovery_state", "")) == "needs_api_original_order_fetch_to_quarantine"
    ]
    api_quarantine_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("original_order_recovery_state", "")) == "api_quarantine_original_order_proof_exists"
    ]
    incomplete_quarantine_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("original_order_recovery_state", "")) == "api_quarantine_original_order_incomplete"
    ]
    raw_compiled_gap_rows = [
        row for row in proof_rows if _mot_text(row.get("original_order_recovery_state", "")) == "local_raw_order_seen_compiled_gap"
    ]
    local_allocation_gap_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("original_order_recovery_state", "")) == "local_order_seen_but_allocation_missing"
    ]
    promotion_decision_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("original_order_recovery_state", "")) == "protected_promotion_decision_needed"
    ]
    duplicate_risk_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("original_order_recovery_state", "")) == "quarantine_duplicate_risk_blocks_recovery"
    ]
    if not proof_path.exists():
        status = "not_checked"
        value = "waiting_for_original_order_recovery_proof"
        root = "The original-order recovery proof has not yet been built for refund rows missing original order proof."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_original_order_recovery_proof_schema"
        root = "The original-order recovery proof is missing required manager proof columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The proof is unsafe because it appears to allow live writes, ROI/restocking use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"proof_rows={len(proof_rows)};unclassified_rows={len(unclassified_rows)}"
        root = "Some original-order recovery rows are not classified."
    else:
        status = "ok"
        value = (
            f"proof_rows={len(proof_rows)};"
            f"needs_api_fetch={len(needs_api_fetch_rows)};"
            f"api_quarantine={len(api_quarantine_rows)};"
            f"incomplete_quarantine={len(incomplete_quarantine_rows)};"
            f"raw_compiled_gap={len(raw_compiled_gap_rows)};"
            f"local_allocation_gap={len(local_allocation_gap_rows)};"
            f"promotion_decision={len(promotion_decision_rows)};"
            f"duplicate_risk={len(duplicate_risk_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_order_recovery_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B054_build_original_order_recovery_proof.py",
            expected_output="Read-only proof showing whether refund rows missing original order proof need API fetch, quarantine repair, or protected promotion",
            actual_proof=(
                f"proof_exists={1 if proof_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"proof_rows={len(proof_rows)};"
                f"needs_api_original_order_fetch_rows={len(needs_api_fetch_rows)};"
                f"api_quarantine_original_order_rows={len(api_quarantine_rows)};"
                f"api_quarantine_incomplete_rows={len(incomplete_quarantine_rows)};"
                f"local_raw_order_seen_compiled_gap_rows={len(raw_compiled_gap_rows)};"
                f"local_order_seen_allocation_missing_rows={len(local_allocation_gap_rows)};"
                f"protected_promotion_decision_rows={len(promotion_decision_rows)};"
                f"duplicate_risk_rows={len(duplicate_risk_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(proof_rows)),
            source_path=f"{proof_path};{summary_path}",
            summary="B original-order recovery proof must prove the missing original sale before token repair, stock recovery, ROI, or restocking can use the refund row.",
            root_cause_guess=root,
            manager_action=(
                "Use B054 to create the next bounded B worker packet: API fetch to quarantine first, then protected promotion preview only after proof. "
                "Do not create tokens, run B, write Sheets, align the DB, or feed these rows to ROI/restocking."
            ),
            safe_repair_boundary=(
                "B original-order recovery proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, "
                "price change, queue edit, Sellerboard-final truth, live promotion, or ROI/restocking use."
            ),
        )
    ]


def _b_original_order_recovery_fetch_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    results_path = base / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_results.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_summary.csv"
    manifest_path = base / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_manifest.json"
    result_rows = read_csv_rows(results_path)
    headers = csv_headers(results_path) or []
    required = {
        "order_id",
        "sku",
        "source_state",
        "action_state",
        "proof_label",
        "required_field_gaps",
        "live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in result_rows
        if not _mot_text(row.get("action_state", ""))
        or not _mot_text(row.get("proof_label", ""))
        or not _mot_text(row.get("source_state", ""))
    ]
    live_write_rows = [row for row in result_rows if _mot_text(row.get("live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in result_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in result_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    planned_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "planned_api_fetch_to_quarantine"]
    fetched_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "fetched_api_proved_to_quarantine"]
    already_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "already_api_proved_in_quarantine"]
    failed_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "api_fetch_failed"]
    duplicate_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "blocked_duplicate_quarantine_rows"]
    incomplete_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "fetched_but_incomplete_quarantine_proof"]
    live_existing_rows = [row for row in result_rows if _mot_text(row.get("action_state", "")) == "blocked_already_in_live_orders"]
    if not results_path.exists():
        status = "not_checked"
        value = "waiting_for_original_order_recovery_fetch_preview"
        root = "The original-order fetch-to-quarantine preview has not yet been built."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_original_order_recovery_fetch_schema"
        root = "The original-order fetch result is missing required manager proof columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The fetch result is unsafe because it appears to allow live writes, ROI/restocking use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"result_rows={len(result_rows)};unclassified_rows={len(unclassified_rows)}"
        root = "Some original-order fetch result rows are not classified."
    elif failed_rows or duplicate_rows or incomplete_rows:
        status = "fail"
        value = (
            f"result_rows={len(result_rows)};"
            f"api_failed={len(failed_rows)};"
            f"duplicate_blocked={len(duplicate_rows)};"
            f"incomplete={len(incomplete_rows)}"
        )
        root = "The fetch-to-quarantine step did not produce clean API proof for every target row."
    else:
        status = "ok"
        value = (
            f"result_rows={len(result_rows)};"
            f"planned={len(planned_rows)};"
            f"fetched={len(fetched_rows)};"
            f"already_quarantined={len(already_rows)};"
            f"already_live={len(live_existing_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_order_recovery_fetch",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B055_fetch_original_orders_to_quarantine.py",
            expected_output="Guarded B original-order API fetch-to-quarantine preview or result",
            actual_proof=(
                f"results_exists={1 if results_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"manifest_exists={1 if manifest_path.exists() else 0};"
                f"result_rows={len(result_rows)};"
                f"planned_api_fetch_rows={len(planned_rows)};"
                f"fetched_api_proved_rows={len(fetched_rows)};"
                f"already_api_proved_rows={len(already_rows)};"
                f"already_live_order_rows={len(live_existing_rows)};"
                f"api_fetch_failed_rows={len(failed_rows)};"
                f"duplicate_blocked_rows={len(duplicate_rows)};"
                f"incomplete_rows={len(incomplete_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(result_rows)),
            source_path=f"{results_path};{summary_path};{manifest_path}",
            summary="B original-order fetch must put API proof into quarantine only before any protected live promotion or token repair is considered.",
            root_cause_guess=root,
            manager_action=(
                "Use B055 first as preview, then only run the approved fetch-to-quarantine boundary if allowed. "
                "Do not run B, promote orders, create tokens, write Sheets, align the DB, or feed these rows to ROI/restocking."
            ),
            safe_repair_boundary=(
                "B original-order fetch-to-quarantine proof only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, Sellerboard-final truth, live promotion, or ROI/restocking use."
            ),
        )
    ]


def _b_original_sale_allocation_repair_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "missing_token_rows",
        "shortage_class",
        "repair_lane",
        "repair_readiness",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("repair_lane", ""))
        or not _mot_text(row.get("repair_readiness", ""))
        or not _mot_text(row.get("bounded_worker_task", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    legacy_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("repair_lane", "")) == "protected_legacy_baseline_allocation_candidate"
    ]
    runtime_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("repair_lane", "")) == "protected_runtime_adjustment_allocation_candidate"
    ]
    missing_token_gap_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("repair_lane", "")) == "allocation_gap_missing_token_row_not_visible"
    ]
    missing_cost_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("repair_lane", "")) == "allocation_gap_missing_cost_basis"
    ]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_original_sale_allocation_repair_preview"
        root = "The original sale allocation repair preview has not yet been built."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_original_sale_allocation_repair_preview_schema"
        root = "The original sale allocation repair preview is missing required manager proof columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The preview is unsafe because it appears to allow live writes, ROI/restocking use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified_rows={len(unclassified_rows)}"
        root = "Some original sale allocation preview rows are not classified."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"legacy_baseline={len(legacy_rows)};"
            f"runtime_adjustment={len(runtime_rows)};"
            f"missing_token_gap={len(missing_token_gap_rows)};"
            f"missing_cost={len(missing_cost_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_sale_allocation_repair_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B056_build_original_sale_allocation_repair_preview.py",
            expected_output="Read-only preview classifying refund rows that have original orders but lack original sale-token allocation proof",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"legacy_baseline_candidate_rows={len(legacy_rows)};"
                f"runtime_adjustment_candidate_rows={len(runtime_rows)};"
                f"missing_token_gap_rows={len(missing_token_gap_rows)};"
                f"missing_cost_rows={len(missing_cost_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="B original sale allocation proof must use the existing token route; refund/order proof alone cannot create reusable stock or final ROI confidence.",
            root_cause_guess=root,
            manager_action=(
                "Use B056 to create the next bounded token-allocation worker packet. Do not create tokens, run B, write Sheets, "
                "align the DB, or let these rows affect ROI/restocking without protected approval."
            ),
            safe_repair_boundary=(
                "B original sale allocation preview only; no token correction, B run, Sheet write, local DB alignment, output deletion, "
                "price change, queue edit, Sellerboard-final truth, or ROI/restocking use."
            ),
        )
    ]


def _b_original_sale_allocation_repair_apply_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv"
    applied_path = base / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_applied.csv"
    manifest_path = base / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_manifest.json"
    preview_rows = read_csv_rows(preview_path)
    applied_rows = read_csv_rows(applied_path)
    applied_headers = csv_headers(applied_path) or []
    manifest = _read_json(manifest_path)
    manifest_status = _mot_text(manifest.get("status", ""))
    required_applied = {
        "order_id",
        "sku",
        "repair_lane",
        "new_token_id",
        "new_token_status",
        "approval_reference",
        "action",
        "runtime_stock_adjustment_closed",
    }
    missing_applied_schema = sorted(required_applied - set(applied_headers)) if applied_path.exists() else []
    created_token_rows = _mot_int(manifest.get("created_token_rows", "0"))
    allocated_token_rows = _mot_int(manifest.get("allocated_token_rows", "0"))
    cogs_rows = _mot_int(manifest.get("cogs_rows", "0"))
    blocked_rows = _mot_int(manifest.get("blocked_rows", "0"))
    runtime_deferred_rows = _mot_int(manifest.get("runtime_adjustment_deferred_rows", "0"))
    preview_count = _mot_int(manifest.get("preview_rows", str(len(preview_rows))))
    reasons = manifest.get("reasons", [])
    if isinstance(reasons, list):
        reason_text = ";".join(str(item) for item in reasons[:3])
    else:
        reason_text = _mot_text(reasons)

    if not manifest_path.exists():
        if preview_rows:
            status = "decision_needed"
            value = f"protected_apply_not_started;preview_rows={len(preview_rows)}"
            root = "The B056 preview has rows, but protected allocation repair has not been applied."
            luke = "1"
        else:
            status = "not_checked"
            value = "waiting_for_original_sale_allocation_apply_manifest"
            root = "No protected original sale allocation apply manifest exists yet."
            luke = "0"
    elif manifest_status == "applied" and missing_applied_schema:
        status = "fail"
        value = "missing_or_invalid_original_sale_allocation_apply_schema"
        root = "The apply manifest says applied, but the applied proof file is missing required manager proof columns."
        luke = "0"
    elif manifest_status == "applied" and (
        blocked_rows
        or created_token_rows != preview_count
        or allocated_token_rows != preview_count
        or cogs_rows != preview_count
        or len(applied_rows) != preview_count
    ):
        status = "fail"
        value = (
            f"manifest=applied;preview_rows={preview_count};created={created_token_rows};"
            f"allocated={allocated_token_rows};cogs={cogs_rows};applied_rows={len(applied_rows)};blocked={blocked_rows}"
        )
        root = "The protected apply counts do not reconcile."
        luke = "0"
    elif manifest_status == "applied":
        status = "ok"
        value = (
            f"manifest=applied;preview_rows={preview_count};created={created_token_rows};"
            f"allocated={allocated_token_rows};cogs={cogs_rows};runtime_deferred={runtime_deferred_rows}"
        )
        root = ""
        luke = "0"
    elif manifest_status in {"blocked_needs_approval", "blocked_active_b_owner"}:
        status = "decision_needed"
        value = f"manifest={manifest_status};preview_rows={preview_count};reason={reason_text}"
        root = "Protected allocation repair needs an approved maintenance window before it can write."
        luke = "1"
    else:
        status = "fail"
        value = f"manifest={manifest_status or 'missing_status'};preview_rows={preview_count};reason={reason_text}"
        root = "The protected allocation repair did not apply cleanly."
        luke = "0"

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_sale_allocation_repair_apply",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B057_apply_original_sale_allocation_repair.py",
            expected_output="Protected apply manifest proving B056 rows were converted into original sale-token allocation proof",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"applied_exists={1 if applied_path.exists() else 0};"
                f"manifest_exists={1 if manifest_path.exists() else 0};"
                f"manifest_status={manifest_status};"
                f"preview_rows={preview_count};"
                f"applied_rows={len(applied_rows)};"
                f"created_token_rows={created_token_rows};"
                f"allocated_token_rows={allocated_token_rows};"
                f"cogs_rows={cogs_rows};"
                f"runtime_adjustment_deferred_rows={runtime_deferred_rows};"
                f"blocked_rows={blocked_rows};"
                f"missing_applied_schema={';'.join(missing_applied_schema)}"
            ),
            row_count=str(len(applied_rows)),
            source_path=f"{preview_path};{applied_path};{manifest_path}",
            summary="B original sale allocation repair is proved only by a protected apply manifest and matching token allocation proof.",
            root_cause_guess=root,
            manager_action=(
                "Use B057 only inside an approved protected maintenance window. Keep runtime stock-adjustment clues visible "
                "unless a separate proof lane closes them."
            ),
            luke_action_required=luke,
            safe_repair_boundary=(
                "B057 original sale allocation repair only; no B run/restart, Sheet write, local DB alignment, output deletion, "
                "price change, queue edit, Sellerboard-final truth, or ROI/restocking use."
            ),
        )
    ]


def _b_refund_token_reproof_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "source_repair_lane",
        "reproof_lane",
        "reproof_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("reproof_lane", ""))
        or not _mot_text(row.get("reproof_readiness", ""))
        or not _mot_text(row.get("preview_action", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    ready_order_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "b008_refund_token_marking"]
    ready_state_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "b008_event_ledger_state_drift"]
    allocation_gap_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "original_allocation_gap"]
    token_ledger_gap_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "token_ledger_gap"]
    token_conflict_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "token_state_conflict"]
    already_pending_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "already_returned_pending"]
    already_closed_rows = [row for row in preview_rows if _mot_text(row.get("reproof_lane", "")) == "already_closed_or_reused"]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_refund_token_reproof_preview"
        root = "B008 refund-token warning rows have not yet been turned into safe reproof-preview lanes."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_refund_token_reproof_preview_schema"
        root = "B008 refund-token reproof preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The B008 preview is unsafe because it appears to allow a live write, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified={len(unclassified_rows)}"
        root = "Some B008 refund-token rows still do not have a concrete reproof lane."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"ready_order={len(ready_order_rows)};"
            f"ready_state={len(ready_state_rows)};"
            f"allocation_gap={len(allocation_gap_rows)};"
            f"token_ledger_gap={len(token_ledger_gap_rows)};"
            f"token_conflict={len(token_conflict_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_refund_token_reproof_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B042_build_refund_token_reproof_preview.py",
            expected_output="Read-only B008 refund-token reproof preview with no live write, no ROI use, and no Sellerboard-as-final truth",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"ready_b008_order_sku_reproof_rows={len(ready_order_rows)};"
                f"ready_b008_state_reproof_rows={len(ready_state_rows)};"
                f"allocation_gap_rows={len(allocation_gap_rows)};"
                f"token_ledger_gap_rows={len(token_ledger_gap_rows)};"
                f"token_state_conflict_rows={len(token_conflict_rows)};"
                f"already_pending_rows={len(already_pending_rows)};"
                f"already_closed_or_reused_rows={len(already_closed_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="B008 refund-token rows should have original allocation and current token-state proof before any protected B008 repair is proposed.",
            root_cause_guess=root,
            manager_action=(
                "Use this preview to create a bounded B008 worker packet. "
                "Do not hand-edit tokens or feed unproved stock recovery into ROI."
            ),
            safe_repair_boundary=(
                "B008 refund-token reproof preview only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_b008_token_ledger_gap_review_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "B" / "refunds" / "b_b008_token_ledger_gap_review.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_b008_token_ledger_gap_review_summary.csv"
    review_rows = read_csv_rows(review_path)
    headers = csv_headers(review_path) or []
    required = {
        "order_id",
        "sku",
        "allocation_token_id",
        "allocation_row_seen",
        "ledger_token_seen",
        "gap_label",
        "manager_state",
        "protected_before_apply",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in review_rows
        if not _mot_text(row.get("gap_label", ""))
        or not _mot_text(row.get("manager_state", ""))
        or not _mot_text(row.get("bounded_worker_task", ""))
    ]
    live_write_rows = [row for row in review_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in review_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in review_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    protected_rows = [row for row in review_rows if _mot_text(row.get("protected_before_apply", "")) == "1"]
    not_yet_rows = [row for row in review_rows if _mot_text(row.get("manager_state", "")) == "not_yet_proven"]
    ledger_alignment_rows = [
        row for row in review_rows if "ledger_alignment" in _mot_text(row.get("manager_state", ""))
    ]
    if not review_path.exists():
        status = "not_checked"
        value = "waiting_for_b008_token_ledger_gap_review"
        root = "B042 token-ledger-gap rows have not yet been turned into a manager proof review."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_b008_token_ledger_gap_review_schema"
        root = "B008 token-ledger gap review is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The B008 token-ledger gap review is unsafe because it appears to allow live write, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"review_rows={len(review_rows)};unclassified={len(unclassified_rows)}"
        root = "Some B008 token-ledger gap rows are still not classified."
    else:
        status = "ok"
        value = (
            f"review_rows={len(review_rows)};"
            f"protected_ledger_alignment={len(ledger_alignment_rows)};"
            f"not_yet_proven={len(not_yet_rows)};"
            f"protected_rows={len(protected_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_b008_token_ledger_gap_review",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B072_build_b008_token_ledger_gap_review.py",
            expected_output="Read-only B008 token-ledger gap review with no live write, no ROI use, and no Sellerboard-as-final truth",
            actual_proof=(
                f"review_exists={1 if review_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"review_rows={len(review_rows)};"
                f"protected_ledger_alignment_rows={len(ledger_alignment_rows)};"
                f"not_yet_proven_rows={len(not_yet_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"protected_rows={len(protected_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(review_rows)),
            source_path=f"{review_path};{summary_path}",
            summary="B008 token-ledger-gap rows should be classified before any protected token correction is considered.",
            root_cause_guess=root,
            manager_action=(
                "Keep these rows blocked from stock-recovery trust unless a protected ledger-alignment preview is approved. "
                "Do not create substitute tokens."
            ),
            safe_repair_boundary=(
                "B008 token-ledger gap review only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_original_return_status_conflict_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "unsafe_original_status",
        "reusable_return_token_ids",
        "has_reusable_duplicate_token",
        "review_lane",
        "review_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("review_lane", ""))
        or not _mot_text(row.get("review_readiness", ""))
        or not _mot_text(row.get("preview_action", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    with_duplicate_rows = [row for row in preview_rows if _mot_text(row.get("has_reusable_duplicate_token", "")) == "1"]
    without_duplicate_rows = [row for row in preview_rows if _mot_text(row.get("has_reusable_duplicate_token", "")) != "1"]
    allocated_rows = [row for row in preview_rows if _mot_text(row.get("unsafe_original_status", "")).lower() == "allocated"]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_original_return_status_conflict_preview"
        root = "Protected original returned-token status conflicts have not yet been turned into a no-write token-level preview."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_original_return_status_conflict_preview_schema"
        root = "The original returned-token status conflict preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The original returned-token preview is unsafe because it appears to allow live writes, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified={len(unclassified_rows)}"
        root = "Some original returned-token conflict rows still do not have a concrete review lane."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"with_duplicate={len(with_duplicate_rows)};"
            f"without_duplicate={len(without_duplicate_rows)};"
            f"allocated_original={len(allocated_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_return_status_conflict_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B045_build_original_return_status_conflict_preview.py",
            expected_output="Read-only token-level preview for protected original returned-token live-status conflicts",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"with_reusable_duplicate_rows={len(with_duplicate_rows)};"
                f"without_reusable_duplicate_rows={len(without_duplicate_rows)};"
                f"allocated_unsafe_original_rows={len(allocated_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="Protected original returned-token conflicts should have named token-level proof before any protected lifecycle correction is proposed.",
            root_cause_guess=root,
            manager_action=(
                "Use this no-write preview to prepare a protected B008/B009 lifecycle repair packet. "
                "Do not correct tokens or feed unproved stock recovery into ROI."
            ),
            safe_repair_boundary=(
                "B original returned-token conflict preview only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_original_return_status_apply_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "current_status",
        "target_status",
        "target_status_source",
        "apply_preview_lane",
        "apply_preview_readiness",
        "block_reason",
        "maintenance_required_before_apply",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("apply_preview_lane", ""))
        or not _mot_text(row.get("apply_preview_readiness", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    missing_stop_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("maintenance_required_before_apply", "")) != "1"
        or _mot_text(row.get("requires_luke_live_apply", "")) != "1"
        or _mot_text(row.get("protected_before_apply", "")) != "1"
    ]
    ready_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("apply_preview_lane", "")) == "original_return_status_apply_preview_ready"
    ]
    blocked_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("apply_preview_lane", "")) != "original_return_status_apply_preview_ready"
    ]
    returned_complete_rows = [row for row in preview_rows if _mot_text(row.get("target_status", "")) == "returned_complete"]
    unsellable_rows = [row for row in preview_rows if _mot_text(row.get("target_status", "")) == "unsellable"]
    research_rows = [row for row in preview_rows if _mot_text(row.get("target_status", "")) == "research_pending"]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_original_return_status_apply_preview"
        root = "Protected original returned-token conflicts have not yet been turned into a no-write apply preview."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_original_return_status_apply_preview_schema"
        root = "The original returned-token apply preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows or missing_stop_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)};"
            f"missing_stop_rows={len(missing_stop_rows)}"
        )
        root = "The original returned-token apply preview is unsafe because it is missing protected stops or appears to allow live use."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified={len(unclassified_rows)}"
        root = "Some original returned-token apply preview rows are not classified."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"ready_apply={len(ready_rows)};"
            f"blocked={len(blocked_rows)};"
            f"target_returned_complete={len(returned_complete_rows)};"
            f"target_unsellable={len(unsellable_rows)};"
            f"target_research_pending={len(research_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_original_return_status_apply_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B063_build_original_return_status_apply_preview.py",
            expected_output="Read-only apply preview for protected original returned-token lifecycle repair",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"ready_apply_rows={len(ready_rows)};"
                f"blocked_rows={len(blocked_rows)};"
                f"target_returned_complete_rows={len(returned_complete_rows)};"
                f"target_unsellable_rows={len(unsellable_rows)};"
                f"target_research_pending_rows={len(research_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"missing_stop_rows={len(missing_stop_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="Protected original returned-token repairs must have a no-write apply preview before any live token status correction.",
            root_cause_guess=root,
            manager_action=(
                "Use this preview to decide whether a future protected B046 apply window is safe. "
                "Do not correct tokens or feed unproved stock recovery into ROI."
            ),
            safe_repair_boundary=(
                "B original returned-token apply preview only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_disposition_conflict_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "amazon_return_disposition",
        "unsafe_original_token_ids",
        "reusable_return_token_ids",
        "reusable_return_token_allocated_order_ids",
        "return_cogs_token_ids",
        "conflict_lane",
        "review_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("conflict_lane", ""))
        or not _mot_text(row.get("review_readiness", ""))
        or not _mot_text(row.get("preview_action", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    reusable_rows = [row for row in preview_rows if _mot_text(row.get("reusable_return_token_ids", ""))]
    allocated_reusable_rows = [row for row in preview_rows if _mot_text(row.get("reusable_return_token_allocated_order_ids", ""))]
    cogs_rows = [row for row in preview_rows if _mot_text(row.get("return_cogs_rows", "")) not in {"", "0"}]
    customer_damaged_rows = [
        row for row in preview_rows if _mot_text(row.get("amazon_return_disposition", "")).upper() == "CUSTOMER_DAMAGED"
    ]
    defective_rows = [row for row in preview_rows if _mot_text(row.get("amazon_return_disposition", "")).upper() == "DEFECTIVE"]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_disposition_conflict_preview"
        root = "Protected non-sellable return conflicts have not yet been turned into a no-write token-level preview."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_disposition_conflict_preview_schema"
        root = "The non-sellable disposition conflict preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The disposition conflict preview is unsafe because it appears to allow live writes, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified={len(unclassified_rows)}"
        root = "Some non-sellable disposition conflict rows still do not have a concrete review lane."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"reusable_token_rows={len(reusable_rows)};"
            f"allocated_reusable_token_rows={len(allocated_reusable_rows)};"
            f"return_cogs_rows={len(cogs_rows)};"
            f"customer_damaged={len(customer_damaged_rows)};"
            f"defective={len(defective_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_disposition_conflict_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B058_build_disposition_conflict_preview.py",
            expected_output="Read-only token-level preview for non-sellable Amazon returns that still have reusable-stock proof",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"reusable_token_rows={len(reusable_rows)};"
                f"allocated_reusable_token_rows={len(allocated_reusable_rows)};"
                f"return_cogs_rows={len(cogs_rows)};"
                f"customer_damaged_rows={len(customer_damaged_rows)};"
                f"defective_rows={len(defective_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="Non-sellable Amazon returns must not become reusable stock unless a protected correction or exception is approved.",
            root_cause_guess=root,
            manager_action=(
                "Use this no-write preview to prepare a protected disposition-conflict correction or exception packet. "
                "Do not correct tokens or feed unproved stock recovery into ROI."
            ),
            safe_repair_boundary=(
                "B disposition conflict preview only; no B run, Sheet write, local DB alignment, output deletion, "
                "token correction, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_disposition_conflict_decision_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "order_id",
        "sku",
        "decision_lane",
        "recommended_manager_position",
        "correction_option",
        "exception_option",
        "impact_summary",
        "protected_decision_required",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("decision_lane", ""))
        or not _mot_text(row.get("recommended_manager_position", ""))
        or not _mot_text(row.get("impact_summary", ""))
    ]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    decision_rows = [row for row in preview_rows if _mot_text(row.get("protected_decision_required", "")) == "1"]
    downstream_rows = [row for row in preview_rows if _mot_text(row.get("downstream_allocated_order_ids", ""))]
    cogs_rows = [row for row in preview_rows if _mot_text(row.get("return_cogs_rows", "")) not in {"", "0"}]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_disposition_conflict_decision_preview"
        root = "Protected non-sellable return conflicts have not yet been turned into a correction/exception decision preview."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_disposition_conflict_decision_preview_schema"
        root = "The non-sellable disposition decision preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The decision preview is unsafe because it appears to allow live writes, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows:
        status = "fail"
        value = f"preview_rows={len(preview_rows)};unclassified={len(unclassified_rows)}"
        root = "Some non-sellable disposition decision rows still do not have concrete decision lanes."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"protected_decisions={len(decision_rows)};"
            f"downstream_allocated={len(downstream_rows)};"
            f"return_cogs={len(cogs_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_disposition_conflict_decision_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B059_build_disposition_conflict_decision_preview.py",
            expected_output="Read-only correction/exception decision preview for non-sellable returned stock already reused by B",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"protected_decision_rows={len(decision_rows)};"
                f"downstream_allocated_rows={len(downstream_rows)};"
                f"return_cogs_rows={len(cogs_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="Non-sellable returned-stock reuse that affects downstream orders needs a protected correction or exception decision before live data changes.",
            root_cause_guess=root,
            manager_action=(
                "Use this no-write preview to prepare a Luke decision packet. Do not correct tokens, COGS, downstream orders, "
                "or ROI/restocking from this preview."
            ),
            safe_repair_boundary=(
                "B disposition conflict decision preview only; no token correction, downstream order correction, B run, "
                "Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_disposition_correction_impact_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reusable_return_token_ids",
        "reusable_token_statuses",
        "downstream_allocated_order_ids",
        "downstream_order_statuses",
        "downstream_order_header_seen_rows",
        "downstream_order_item_match_rows",
        "return_cogs_rows",
        "correction_impact_lane",
        "correction_preview_action",
        "correction_blocker",
        "future_apply_scope",
        "protected_decision_required",
        "would_touch_live_outputs",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("correction_impact_lane", ""))
        or not _mot_text(row.get("correction_preview_action", ""))
        or not _mot_text(row.get("correction_blocker", ""))
        or not _mot_text(row.get("future_apply_scope", ""))
    ]
    unprotected_rows = [row for row in preview_rows if _mot_text(row.get("protected_decision_required", "")) != "1"]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    downstream_rows = [row for row in preview_rows if _mot_text(row.get("downstream_allocated_order_ids", ""))]
    downstream_header_rows = [
        row for row in preview_rows if _mot_text(row.get("downstream_order_header_seen_rows", "")) not in {"", "0"}
    ]
    downstream_item_rows = [
        row for row in preview_rows if _mot_text(row.get("downstream_order_item_match_rows", "")) not in {"", "0"}
    ]
    cogs_rows = [row for row in preview_rows if _mot_text(row.get("return_cogs_rows", "")) not in {"", "0"}]
    decision_rows = [row for row in preview_rows if _mot_text(row.get("protected_decision_required", "")) == "1"]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_disposition_correction_impact_preview"
        root = "The protected correction decision has not yet been expanded into downstream correction-impact proof."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_disposition_correction_impact_preview_schema"
        root = "The downstream correction-impact preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The correction-impact preview is unsafe because it appears to allow live writes, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows or unprotected_rows:
        status = "fail"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"unclassified={len(unclassified_rows)};"
            f"unprotected={len(unprotected_rows)}"
        )
        root = "Some downstream correction-impact rows still do not have a protected review lane."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"protected_decisions={len(decision_rows)};"
            f"downstream_allocated={len(downstream_rows)};"
            f"downstream_headers_seen={len(downstream_header_rows)};"
            f"downstream_items_seen={len(downstream_item_rows)};"
            f"return_cogs={len(cogs_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_disposition_correction_impact_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B060_build_disposition_correction_impact_preview.py",
            expected_output="Read-only downstream impact preview for protected non-sellable return correction review",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"protected_decision_rows={len(decision_rows)};"
                f"downstream_allocated_rows={len(downstream_rows)};"
                f"downstream_header_seen_rows={len(downstream_header_rows)};"
                f"downstream_item_seen_rows={len(downstream_item_rows)};"
                f"return_cogs_rows={len(cogs_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"unprotected_rows={len(unprotected_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="Protected non-sellable return correction review must show downstream order and COGS impact before any live repair is proposed.",
            root_cause_guess=root,
            manager_action=(
                "Use this no-write impact preview to scope a protected correction review. Do not correct tokens, COGS, "
                "downstream allocation, ROI, or restocking state from this preview."
            ),
            safe_repair_boundary=(
                "B correction-impact preview only; no token correction, downstream order correction, COGS correction, B run, "
                "Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_disposition_correction_apply_preview_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview_summary.csv"
    preview_rows = read_csv_rows(preview_path)
    headers = csv_headers(preview_path) or []
    required = {
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reused_token_id",
        "downstream_order_id",
        "downstream_order_status",
        "downstream_order_date",
        "reused_token_allocation_rows",
        "reused_token_cogs_rows",
        "replacement_candidate_token_id",
        "replacement_candidate_date_relation",
        "replacement_candidate_days_after_order",
        "replacement_date_validation_reason",
        "replacement_available_token_count",
        "replacement_before_order_count",
        "replacement_unknown_date_count",
        "correction_apply_lane",
        "correction_preview_action",
        "protected_decision_required",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row
        for row in preview_rows
        if not _mot_text(row.get("correction_apply_lane", ""))
        or not _mot_text(row.get("correction_preview_action", ""))
    ]
    unprotected_rows = [row for row in preview_rows if _mot_text(row.get("protected_decision_required", "")) != "1"]
    live_apply_rows = [row for row in preview_rows if _mot_text(row.get("requires_luke_live_apply", "")) != "1"]
    live_write_rows = [row for row in preview_rows if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}]
    roi_rows = [row for row in preview_rows if _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}]
    sellerboard_rows = [row for row in preview_rows if _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}]
    replacement_ready_rows = [
        row for row in preview_rows if _mot_text(row.get("correction_apply_lane", "")).endswith("replacement_swap_preview_ready")
    ]
    date_validation_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("correction_apply_lane", "")) == "replacement_candidate_date_validation_required"
    ]
    no_replacement_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("correction_apply_lane", "")) == "no_replacement_token_protected_shortage_or_exception_review"
    ]
    candidate_after_order_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("replacement_candidate_date_relation", "")) == "after_downstream_order"
    ]
    candidate_unknown_timing_rows = [
        row
        for row in preview_rows
        if _mot_text(row.get("replacement_candidate_date_relation", ""))
        in {"missing_downstream_order_date", "unknown_replacement_date"}
    ]
    if not preview_path.exists():
        status = "not_checked"
        value = "waiting_for_disposition_correction_apply_preview"
        root = "The downstream correction-impact proof has not yet been turned into a protected no-write apply preview."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_disposition_correction_apply_preview_schema"
        root = "The protected correction apply preview is missing required safety columns."
    elif live_write_rows or roi_rows or sellerboard_rows:
        status = "fail"
        value = (
            f"live_write_rows={len(live_write_rows)};"
            f"roi_rows={len(roi_rows)};"
            f"sellerboard_rows={len(sellerboard_rows)}"
        )
        root = "The protected correction apply preview is unsafe because it appears to allow live writes, ROI/restock use, or Sellerboard-as-final truth."
    elif unclassified_rows or unprotected_rows or live_apply_rows:
        status = "fail"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"unclassified={len(unclassified_rows)};"
            f"unprotected={len(unprotected_rows)};"
            f"missing_live_apply_stop={len(live_apply_rows)}"
        )
        root = "Some correction apply preview rows are not safely classified as protected preview-only work."
    else:
        status = "ok"
        value = (
            f"preview_rows={len(preview_rows)};"
            f"replacement_ready={len(replacement_ready_rows)};"
            f"date_validation={len(date_validation_rows)};"
            f"candidate_after_order={len(candidate_after_order_rows)};"
            f"candidate_unknown_timing={len(candidate_unknown_timing_rows)};"
            f"no_replacement={len(no_replacement_rows)}"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_disposition_correction_apply_preview",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B061_build_disposition_correction_apply_preview.py",
            expected_output="Read-only protected apply preview for non-sellable returned-stock correction lanes",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"preview_rows={len(preview_rows)};"
                f"replacement_ready_rows={len(replacement_ready_rows)};"
                f"date_validation_rows={len(date_validation_rows)};"
                f"candidate_after_order_rows={len(candidate_after_order_rows)};"
                f"candidate_unknown_timing_rows={len(candidate_unknown_timing_rows)};"
                f"no_replacement_rows={len(no_replacement_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"unprotected_rows={len(unprotected_rows)};"
                f"missing_live_apply_stop_rows={len(live_apply_rows)};"
                f"live_write_rows={len(live_write_rows)};"
                f"roi_rows={len(roi_rows)};"
                f"sellerboard_final_truth_rows={len(sellerboard_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(preview_rows)),
            source_path=f"{preview_path};{summary_path}",
            summary="Protected correction apply preview must prove replacement-token availability or keep rows in shortage/exception review before any live correction.",
            root_cause_guess=root,
            manager_action=(
                "Use this no-write apply preview to decide whether a future protected live correction can swap tokens or must stay as a shortage/exception. "
                "Do not apply the correction from this preview."
            ),
            safe_repair_boundary=(
                "B correction apply preview only; no token correction, replacement-token swap, downstream allocation correction, "
                "COGS correction, B run, Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_historical_replacement_stock_proof_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    proof_path = base / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof_summary.csv"
    proof_rows = read_csv_rows(proof_path)
    headers = csv_headers(proof_path) or []
    required = {
        "return_order_id",
        "sku",
        "downstream_order_id",
        "downstream_order_date",
        "reused_token_id",
        "visible_replacement_candidate_token_id",
        "visible_replacement_candidate_received_date",
        "visible_replacement_candidate_date_relation",
        "historical_replacement_label",
        "direct_replacement_swap_ready",
        "historical_candidate_token_id",
        "historical_candidate_received_date",
        "historical_candidate_status",
        "historical_candidate_allocated_order_id",
        "historical_candidate_allocation_date",
        "historical_candidate_cogs_rows",
        "historical_candidate_days_before_downstream_sale",
        "candidate_pool_currently_available_before_count",
        "candidate_pool_used_later_count",
        "candidate_pool_late_available_count",
        "candidate_pool_missing_date_count",
        "proof_reason",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    safe_labels = {
        "date_valid_currently_available",
        "date_valid_but_already_used_later",
        "replacement_arrived_after_sale",
        "missing_date_proof",
        "not_yet_proven",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [
        row for row in proof_rows if _mot_text(row.get("historical_replacement_label", "")) not in safe_labels
    ]
    direct_ready_rows = [
        row for row in proof_rows if _mot_text(row.get("direct_replacement_swap_ready", "")) == "1"
    ]
    currently_available_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("historical_replacement_label", "")) == "date_valid_currently_available"
    ]
    used_later_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("historical_replacement_label", "")) == "date_valid_but_already_used_later"
    ]
    late_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("historical_replacement_label", "")) == "replacement_arrived_after_sale"
    ]
    missing_date_rows = [
        row for row in proof_rows if _mot_text(row.get("historical_replacement_label", "")) == "missing_date_proof"
    ]
    not_proven_rows = [
        row for row in proof_rows if _mot_text(row.get("historical_replacement_label", "")) == "not_yet_proven"
    ]
    ready_mismatch_rows = [
        row
        for row in proof_rows
        if (
            _mot_text(row.get("historical_replacement_label", "")) == "date_valid_currently_available"
            and _mot_text(row.get("direct_replacement_swap_ready", "")) != "1"
        )
        or (
            _mot_text(row.get("historical_replacement_label", "")) != "date_valid_currently_available"
            and _mot_text(row.get("direct_replacement_swap_ready", "")) not in {"", "0"}
        )
    ]
    unsafe_rows = [
        row
        for row in proof_rows
        if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}
    ]
    unprotected_rows = [
        row for row in proof_rows if _mot_text(row.get("protected_before_apply", "")) != "1"
    ]
    parked_rows = used_later_rows + late_rows + missing_date_rows + not_proven_rows
    if not proof_path.exists():
        status = "not_checked"
        value = "waiting_for_historical_replacement_stock_proof"
        root = "The historical replacement-stock proof has not been built yet."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_historical_replacement_stock_proof_schema"
        root = "The historical replacement-stock proof is missing required manager safety columns."
    elif unsafe_rows or unclassified_rows or ready_mismatch_rows or unprotected_rows:
        status = "fail"
        value = (
            f"proof_rows={len(proof_rows)};"
            f"unsafe_rows={len(unsafe_rows)};"
            f"unclassified={len(unclassified_rows)};"
            f"ready_mismatch={len(ready_mismatch_rows)};"
            f"unprotected={len(unprotected_rows)}"
        )
        root = "The historical replacement-stock proof is unsafe or not cleanly classified."
    elif parked_rows:
        status = "warn"
        value = (
            f"proof_rows={len(proof_rows)};"
            f"date_valid_available={len(currently_available_rows)};"
            f"used_later={len(used_later_rows)};"
            f"late={len(late_rows)};"
            f"missing_date={len(missing_date_rows)};"
            f"not_yet_proven={len(not_proven_rows)}"
        )
        root = "Some rows are classified but not direct replacement-swap-ready, so they must stay parked unless a future protected decision changes them."
    else:
        status = "ok"
        value = (
            f"proof_rows={len(proof_rows)};"
            f"date_valid_available={len(currently_available_rows)};"
            f"used_later=0;late=0;missing_date=0;not_yet_proven=0"
        )
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_historical_replacement_stock_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B065_build_historical_replacement_stock_proof.py",
            expected_output="Read-only proof classifying historical replacement-stock candidates before any live token correction",
            actual_proof=(
                f"proof_exists={1 if proof_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"proof_rows={len(proof_rows)};"
                f"date_valid_currently_available_rows={len(currently_available_rows)};"
                f"date_valid_but_already_used_later_rows={len(used_later_rows)};"
                f"replacement_arrived_after_sale_rows={len(late_rows)};"
                f"missing_date_proof_rows={len(missing_date_rows)};"
                f"not_yet_proven_rows={len(not_proven_rows)};"
                f"direct_ready_rows={len(direct_ready_rows)};"
                f"unsafe_rows={len(unsafe_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"ready_mismatch_rows={len(ready_mismatch_rows)};"
                f"unprotected_rows={len(unprotected_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(proof_rows)),
            source_path=f"{proof_path};{summary_path}",
            summary="B historical replacement proof must separate date-valid stock from late, already-used, missing-date, or unproved stock without making a live token swap.",
            root_cause_guess=root,
            manager_action=(
                "Use this proof to park or scope a future protected correction. Do not swap tokens, correct allocations or COGS, "
                "write Sheets, align DB facts, or let the proof affect ROI/restocking."
            ),
            safe_repair_boundary=(
                "B historical replacement-stock proof only; no B run, token correction, replacement swap, allocation change, "
                "COGS correction, Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_no_replacement_shortage_exception_review_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review_summary.csv"
    review_rows = read_csv_rows(review_path)
    headers = csv_headers(review_path) or []
    required = {
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "downstream_order_id",
        "downstream_order_date",
        "reused_token_id",
        "review_label",
        "direct_replacement_swap_ready",
        "candidate_token_id",
        "candidate_received_date",
        "candidate_status",
        "candidate_allocated_order_id",
        "candidate_allocation_date",
        "clean_same_sku_token_count",
        "clean_stock_available_before_count",
        "clean_stock_used_before_sale_count",
        "clean_stock_used_later_count",
        "clean_stock_late_available_count",
        "clean_stock_missing_date_count",
        "reused_token_allocation_rows",
        "reused_token_cogs_rows",
        "return_cogs_rows",
        "proof_reason",
        "manager_expectation",
        "mot_proof_check",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    }
    safe_labels = {
        "true_no_replacement_shortage",
        "replacement_mapping_gap",
        "date_valid_but_already_used_later",
        "replacement_arrived_after_sale",
        "missing_date_proof",
        "not_yet_proven",
    }
    missing_schema = sorted(required - set(headers))
    unclassified_rows = [row for row in review_rows if _mot_text(row.get("review_label", "")) not in safe_labels]
    true_shortage_rows = [
        row for row in review_rows if _mot_text(row.get("review_label", "")) == "true_no_replacement_shortage"
    ]
    mapping_gap_rows = [
        row for row in review_rows if _mot_text(row.get("review_label", "")) == "replacement_mapping_gap"
    ]
    used_later_rows = [
        row for row in review_rows if _mot_text(row.get("review_label", "")) == "date_valid_but_already_used_later"
    ]
    late_rows = [
        row for row in review_rows if _mot_text(row.get("review_label", "")) == "replacement_arrived_after_sale"
    ]
    missing_date_rows = [
        row for row in review_rows if _mot_text(row.get("review_label", "")) == "missing_date_proof"
    ]
    not_proven_rows = [
        row for row in review_rows if _mot_text(row.get("review_label", "")) == "not_yet_proven"
    ]
    unsafe_rows = [
        row
        for row in review_rows
        if _mot_text(row.get("preview_live_write_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("roi_or_restock_use_allowed", "")) not in {"", "0"}
        or _mot_text(row.get("sellerboard_final_truth_allowed", "")) not in {"", "0"}
    ]
    direct_ready_rows = [
        row for row in review_rows if _mot_text(row.get("direct_replacement_swap_ready", "")) not in {"", "0"}
    ]
    unprotected_rows = [
        row for row in review_rows if _mot_text(row.get("protected_before_apply", "")) != "1"
    ]
    if not review_path.exists():
        status = "not_checked"
        value = "waiting_for_no_replacement_shortage_exception_review"
        root = "The no-replacement shortage/exception review has not been built yet."
    elif missing_schema:
        status = "fail"
        value = "missing_or_invalid_no_replacement_shortage_exception_review_schema"
        root = "The no-replacement shortage/exception review is missing required manager safety columns."
    elif unsafe_rows or unclassified_rows or direct_ready_rows or unprotected_rows:
        status = "fail"
        value = (
            f"review_rows={len(review_rows)};"
            f"unsafe_rows={len(unsafe_rows)};"
            f"unclassified={len(unclassified_rows)};"
            f"direct_ready={len(direct_ready_rows)};"
            f"unprotected={len(unprotected_rows)}"
        )
        root = "The no-replacement shortage/exception review is unsafe or not cleanly classified."
    elif review_rows:
        status = "warn"
        value = (
            f"review_rows={len(review_rows)};"
            f"true_shortage={len(true_shortage_rows)};"
            f"mapping_gap={len(mapping_gap_rows)};"
            f"used_later={len(used_later_rows)};"
            f"late={len(late_rows)};"
            f"missing_date={len(missing_date_rows)};"
            f"not_yet_proven={len(not_proven_rows)}"
        )
        root = "The no-replacement row is classified and safe, but it remains parked because no live stock recovery exception is approved."
    else:
        status = "ok"
        value = "review_rows=0;no_no_replacement_rows_visible"
        root = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_no_replacement_shortage_exception_review",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B066_build_no_replacement_shortage_exception_review.py",
            expected_output="Read-only proof classifying no-replacement shortage/exception rows before any live stock decision",
            actual_proof=(
                f"review_exists={1 if review_path.exists() else 0};"
                f"summary_exists={1 if summary_path.exists() else 0};"
                f"review_rows={len(review_rows)};"
                f"true_no_replacement_shortage_rows={len(true_shortage_rows)};"
                f"replacement_mapping_gap_rows={len(mapping_gap_rows)};"
                f"date_valid_but_already_used_later_rows={len(used_later_rows)};"
                f"replacement_arrived_after_sale_rows={len(late_rows)};"
                f"missing_date_proof_rows={len(missing_date_rows)};"
                f"not_yet_proven_rows={len(not_proven_rows)};"
                f"direct_ready_rows={len(direct_ready_rows)};"
                f"unsafe_rows={len(unsafe_rows)};"
                f"unclassified_rows={len(unclassified_rows)};"
                f"unprotected_rows={len(unprotected_rows)};"
                f"missing_schema={';'.join(missing_schema)}"
            ),
            row_count=str(len(review_rows)),
            source_path=f"{review_path};{summary_path}",
            summary="B no-replacement review must prove whether the row is true shortage, mapping gap, missing proof, or protected exception while blocking live stock recovery.",
            root_cause_guess=root,
            manager_action=(
                "Use this review to park the shortage or scope a protected decision. Do not create stock, swap tokens, "
                "correct allocations or COGS, write Sheets, align DB facts, or let the proof affect ROI/restocking."
            ),
            safe_repair_boundary=(
                "B no-replacement shortage/exception proof only; no B run, token creation, token correction, replacement swap, "
                "allocation change, COGS correction, Sheet write, local DB alignment, output deletion, price change, queue edit, or live ROI/restocking use."
            ),
        )
    ]


def _b_disposition_correction_swap_apply_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    preview_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv"
    applied_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_swap_applied.csv"
    manifest_path = base / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_swap_manifest.json"
    preview_rows = read_csv_rows(preview_path)
    applied_rows = read_csv_rows(applied_path)
    applied_headers = csv_headers(applied_path) or []
    manifest = _read_json(manifest_path)
    manifest_status = _mot_text(manifest.get("status", ""))
    required_applied = {
        "return_order_id",
        "sku",
        "downstream_order_id",
        "reused_token_id",
        "replacement_token_id",
        "previous_reused_status",
        "new_reused_status",
        "previous_replacement_status",
        "new_replacement_status",
        "allocation_rows_updated",
        "cogs_rows_updated",
        "correction_apply_lane",
        "action",
    }
    missing_applied_schema = sorted(required_applied - set(applied_headers)) if applied_path.exists() else []
    replacement_ready_rows = [
        row for row in preview_rows if _mot_text(row.get("correction_apply_lane", "")).endswith("replacement_swap_preview_ready")
    ]
    eligible_rows = _mot_int(manifest.get("eligible_rows", str(len(replacement_ready_rows))))
    applied_count = _mot_int(manifest.get("applied_rows", str(len(applied_rows))))
    token_rows_updated = _mot_int(manifest.get("token_rows_updated", "0"))
    allocation_rows_updated = _mot_int(manifest.get("allocation_rows_updated", "0"))
    cogs_rows_updated = _mot_int(manifest.get("cogs_rows_updated", "0"))
    blocked_rows = _mot_int(manifest.get("blocked_rows", "0"))
    reasons = manifest.get("reasons", [])
    reason_text = ";".join(str(item) for item in reasons[:3]) if isinstance(reasons, list) else _mot_text(reasons)
    if not manifest_path.exists():
        if replacement_ready_rows:
            status = "decision_needed"
            value = f"protected_swap_not_started;replacement_ready={len(replacement_ready_rows)}"
            root = "The B061 preview has replacement-swap ready rows, but the protected B062 apply has not been run."
            luke = "1"
        else:
            status = "ok"
            value = "no_replacement_swap_apply_needed"
            root = ""
            luke = "0"
    elif manifest_status == "applied" and missing_applied_schema:
        status = "fail"
        value = "missing_or_invalid_disposition_correction_swap_apply_schema"
        root = "The B062 manifest says applied, but the applied proof file is missing required manager proof columns."
        luke = "0"
    elif manifest_status == "applied" and (
        blocked_rows
        or applied_count != eligible_rows
        or len(applied_rows) != eligible_rows
        or token_rows_updated != eligible_rows * 2
        or allocation_rows_updated != eligible_rows
        or cogs_rows_updated != eligible_rows
    ):
        status = "fail"
        value = (
            f"manifest=applied;eligible={eligible_rows};applied={applied_count};"
            f"token_updates={token_rows_updated};allocation_updates={allocation_rows_updated};"
            f"cogs_updates={cogs_rows_updated};blocked={blocked_rows}"
        )
        root = "The protected B062 apply counts do not reconcile."
        luke = "0"
    elif manifest_status == "applied":
        status = "ok"
        value = (
            f"manifest=applied;eligible={eligible_rows};applied={applied_count};"
            f"token_updates={token_rows_updated};allocation_updates={allocation_rows_updated};"
            f"cogs_updates={cogs_rows_updated}"
        )
        root = ""
        luke = "0"
    elif manifest_status in {"blocked_needs_approval", "blocked_active_b_owner"}:
        status = "decision_needed"
        value = f"manifest={manifest_status};eligible={eligible_rows};reason={reason_text}"
        root = "Protected B062 swap repair needs an approved maintenance window before it can write."
        luke = "1"
    else:
        status = "fail"
        value = f"manifest={manifest_status or 'missing_status'};eligible={eligible_rows};reason={reason_text}"
        root = "The protected B062 swap repair did not apply cleanly."
        luke = "0"
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_disposition_correction_swap_apply",
            status=status,
            severity=_severity(status),
            value=value,
            producer="B062_apply_disposition_correction_swap.py",
            expected_output="Protected apply manifest proving approved non-sellable returned-stock swaps were applied all-or-nothing",
            actual_proof=(
                f"preview_exists={1 if preview_path.exists() else 0};"
                f"applied_exists={1 if applied_path.exists() else 0};"
                f"manifest_exists={1 if manifest_path.exists() else 0};"
                f"manifest_status={manifest_status};"
                f"replacement_ready_preview_rows={len(replacement_ready_rows)};"
                f"eligible_rows={eligible_rows};"
                f"applied_rows={applied_count};"
                f"applied_file_rows={len(applied_rows)};"
                f"token_rows_updated={token_rows_updated};"
                f"allocation_rows_updated={allocation_rows_updated};"
                f"cogs_rows_updated={cogs_rows_updated};"
                f"blocked_rows={blocked_rows};"
                f"missing_applied_schema={';'.join(missing_applied_schema)}"
            ),
            row_count=str(len(applied_rows)),
            source_path=f"{preview_path};{applied_path};{manifest_path}",
            summary="B062 is proved only when the protected replacement-token swaps update token, allocation, and COGS proof together.",
            root_cause_guess=root,
            manager_action=(
                "Use B062 only inside an approved protected maintenance window. Keep date-validation and no-replacement rows parked."
            ),
            luke_action_required=luke,
            safe_repair_boundary=(
                "B062 replacement-token swap only; no B run/restart, Sheet write, local DB alignment, output deletion, "
                "price change, queue edit, Sellerboard-final truth, ROI/restocking use, or parked-row correction."
            ),
        )
    ]


def _b_sellerboard_bridge_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    bridge_dir = base / "out" / "systems" / "M" / "sellerboard_bridge"
    summary_path = bridge_dir / SUMMARY_NAME
    order_path = bridge_dir / ORDER_RECONCILIATION_NAME
    sku_gap_path = bridge_dir / SKU_GAP_NAME
    recovery_summary_path = base / "out" / "systems" / "M" / B_ORDER_RECOVERY_DIR_NAME / B_ORDER_RECOVERY_SUMMARY_CSV_NAME
    if not summary_path.exists():
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_sellerboard_bridge_report",
                status="not_checked",
                severity="info",
                value="missing",
                producer="sellerone_manager.sellerboard_bridge",
                expected_output=f"out/systems/M/sellerboard_bridge/{SUMMARY_NAME}",
                actual_proof="sellerboard_bridge_not_built",
                source_path=str(summary_path),
                summary="Sellerboard bridge proof has not been built yet. This is not B runtime proof.",
                root_cause_guess="Manual or emailed Sellerboard export has not been processed by the manager bridge.",
                manager_action="Build the read-only Sellerboard bridge report when a Sellerboard OrderList CSV is available.",
                safe_repair_boundary="B Sellerboard bridge reporting only; no B run, Sheet write, data correction, or ROI replacement.",
            )
        ]

    summary_rows = read_csv_rows(summary_path)
    metric_rows = {row.get("metric", ""): row for row in summary_rows}
    summary_headers = csv_headers(summary_path) or []
    order_headers = csv_headers(order_path) or []
    sku_gap_headers = csv_headers(sku_gap_path) or []
    age = file_age_hours(summary_path, now)
    report_status = status_from_age(age, warn_hours=36.0, fail_hours=240.0)
    report_value = "fresh_enough" if report_status == "ok" else "stale"
    missing_output_files = [str(path) for path in [order_path, sku_gap_path] if not path.exists()]
    missing_schema = []
    missing_schema.extend(f"summary:{col}" for col in SUMMARY_COLUMNS if col not in summary_headers)
    missing_schema.extend(f"order:{col}" for col in ORDER_RECONCILIATION_COLUMNS if col not in order_headers)
    missing_schema.extend(f"sku_gap:{col}" for col in SKU_GAP_COLUMNS if col not in sku_gap_headers)
    schema_status = "fail" if missing_output_files or missing_schema else "ok"

    required_missing = _summary_metric_int(metric_rows, "required_columns_missing")
    missing_orders = _summary_metric_int(metric_rows, "sellerboard_shipped_missing_from_sellerone_orders")
    unmapped_shipped = _summary_metric_int(metric_rows, "sellerboard_shipped_rows_unmapped_to_sku")
    try:
        recovery_rows = build_b_order_recovery_plan(root=base, observed_utc=observed_utc).summary_rows
    except Exception:
        recovery_rows = read_csv_rows(recovery_summary_path)
    recovery_metrics = {row.get("metric", ""): row for row in recovery_rows}
    api_proved_quarantine = _summary_metric_int(recovery_metrics, "quarantine_api_proved_missing_orders")
    unrecovered_missing = _summary_metric_int(recovery_metrics, "unrecovered_missing_sellerboard_orders")
    recovery_scope_active = bool(api_proved_quarantine or _summary_metric_int(recovery_metrics, "amazon_marketplaces_in_scope"))
    effective_missing = unrecovered_missing if recovery_scope_active else missing_orders
    effective_unmapped = max(unmapped_shipped - api_proved_quarantine, 0) if recovery_scope_active else unmapped_shipped
    order_status = "fail" if required_missing or effective_missing or effective_unmapped else "warn" if missing_orders or unmapped_shipped else "ok"
    order_root = ""
    order_action = "No manager action unless Sellerboard finds a new missing shipped order."
    if order_status == "fail":
        order_root = "Sellerboard has outside order/SKU evidence that SellerOne has not fully matched or recovered."
        order_action = "Create a bounded B bridge task to inspect missing order or SKU mapping proof. Do not backfill, run B, or correct data from MOT."
    elif order_status == "warn":
        order_root = "Sellerboard still shows a live-local gap, but the missing order is API-proved in quarantine."
        order_action = "Keep the gap visible as a protected merge/ROI warning. Do not feed quarantined or bridge values into live ROI without Luke."

    return_missing_refund = _summary_metric_int(metric_rows, "sellerboard_return_orders_missing_local_refund_posted_window")
    fee_detail_rows = _summary_metric_int(metric_rows, "fee_detail_ledger_api_rows")
    refund_nonzero = _summary_metric_int(metric_rows, "roi_expected_refund_nonzero_rows")
    sellerboard_return_rows = _summary_metric_int(metric_rows, "sellerboard_return_rows")
    refund_proof_state = _summary_metric(metric_rows, "refund_proof_state") or "not_reported"
    fee_shipping_proof_state = _summary_metric(metric_rows, "fee_shipping_proof_state") or "not_reported"
    roi_refund_proof_state = _summary_metric(metric_rows, "roi_refund_proof_state") or "not_reported"
    live_roi_safe = _summary_metric(metric_rows, "bridge_values_safe_for_live_roi") or "0"
    refund_api_proof_state = _summary_metric(metric_rows, "refund_api_proof_state") or "not_reported"
    commission_api_proof_state = _summary_metric(metric_rows, "commission_api_proof_state") or "not_reported"
    fba_fee_api_proof_state = _summary_metric(metric_rows, "fba_fee_api_proof_state") or "not_reported"
    other_fee_api_proof_state = _summary_metric(metric_rows, "other_fee_api_proof_state") or "not_reported"
    shipping_income_api_proof_state = _summary_metric(metric_rows, "shipping_income_api_proof_state") or "not_reported"
    shipping_fee_api_proof_state = _summary_metric(metric_rows, "shipping_fee_api_proof_state") or "not_reported"
    roi_money_confidence_state = _summary_metric(metric_rows, "roi_money_confidence_state") or "not_reported"
    money_proof_states = [
        refund_api_proof_state,
        commission_api_proof_state,
        fba_fee_api_proof_state,
        other_fee_api_proof_state,
        shipping_income_api_proof_state,
        shipping_fee_api_proof_state,
        roi_money_confidence_state,
    ]
    money_proof_incomplete = any(
        state in {"not_reported", "not_yet_proven", "sellerboard_bridge_only", "bridge_labelled_only"}
        for state in money_proof_states
    )
    refund_fee_status = (
        "warn"
        if return_missing_refund or fee_detail_rows == 0 or (sellerboard_return_rows and refund_nonzero == 0) or money_proof_incomplete
        else "ok"
    )

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_bridge_report",
            status=report_status,
            severity=_severity(report_status),
            value=report_value,
            producer="sellerone_manager.sellerboard_bridge",
            expected_output=f"out/systems/M/sellerboard_bridge/{SUMMARY_NAME}",
            actual_proof=f"rows={len(summary_rows)};age_hours={_age_text(age)};overall_status={_summary_metric(metric_rows, 'overall_status')}",
            age_hours=_age_text(age),
            row_count=str(len(summary_rows)),
            source_path=str(summary_path),
            summary="Sellerboard bridge report should be current enough to compare B order truth against outside Sellerboard evidence.",
            root_cause_guess="Sellerboard bridge proof is stale." if report_status != "ok" else "",
            manager_action="Refresh the read-only Sellerboard bridge report from the latest available Sellerboard OrderList file.",
            safe_repair_boundary="B Sellerboard bridge reporting only; no B run, Sheet write, data correction, or ROI replacement.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_bridge_schema",
            status=schema_status,
            severity=_severity(schema_status),
            value="missing_schema" if missing_schema else "missing_files" if missing_output_files else "schema_ok",
            producer="sellerone_manager.sellerboard_bridge",
            expected_output="Sellerboard bridge summary, order reconciliation, and SKU gap CSV schemas",
            actual_proof=(
                f"missing_files={';'.join(missing_output_files)};"
                f"missing_columns={';'.join(missing_schema[:25])}"
            ),
            row_count=str(len(summary_rows)),
            source_path=";".join(str(path) for path in [summary_path, order_path, sku_gap_path]),
            summary="Sellerboard bridge outputs must keep stable columns so MOT and workers can trust the report shape.",
            root_cause_guess="The bridge report outputs are missing or have unexpected columns." if schema_status != "ok" else "",
            manager_action="Repair the manager bridge report shape only. Do not alter business outputs to satisfy this check.",
            safe_repair_boundary="Manager bridge schema only; no B run, Sheet write, data correction, or output deletion.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_order_reconciliation",
            status=order_status,
            severity=_severity(order_status),
            value=(
                f"missing_orders={missing_orders};unmapped_shipped={unmapped_shipped};"
                f"api_proved_quarantine={api_proved_quarantine};unrecovered={effective_missing};"
                f"required_columns_missing={required_missing}"
            ),
            producer="sellerone_manager.sellerboard_bridge",
            expected_output="Sellerboard shipped orders map to SellerOne orders and SKUs",
            actual_proof=(
                f"sellerboard_shipped_missing_from_sellerone_orders={missing_orders};"
                f"sellerboard_shipped_rows_unmapped_to_sku={unmapped_shipped};"
                f"quarantine_api_proved_missing_orders={api_proved_quarantine};"
                f"unrecovered_missing_sellerboard_orders={effective_missing};"
                f"required_columns_missing={required_missing}"
            ),
            source_path=f"{summary_path};{recovery_summary_path}",
            summary="Sellerboard outside proof should not show unrecovered shipped orders missing from SellerOne or shipped rows without SKU mapping.",
            root_cause_guess=order_root,
            manager_action=order_action,
            safe_repair_boundary="B Sellerboard reconciliation proof only; no B run, restart, Sheet write, local DB alignment, output deletion, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_refund_fee_roi_bridge",
            status=refund_fee_status,
            severity=_severity(refund_fee_status),
            value=(
                f"return_refund_gap={return_missing_refund};fee_detail_rows={fee_detail_rows};"
                f"roi_refund_rows={refund_nonzero};live_roi_safe={live_roi_safe}"
            ),
            producer="sellerone_manager.sellerboard_bridge",
            expected_output="Refund, shipping, fee, and ROI gap bridge summary",
            actual_proof=(
                f"sellerboard_return_orders_missing_local_refund_posted_window={return_missing_refund};"
                f"fee_detail_ledger_api_rows={fee_detail_rows};"
                f"roi_expected_refund_nonzero_rows={refund_nonzero};"
                f"sellerboard_return_rows={sellerboard_return_rows};"
                f"refund_api_proof_state={refund_api_proof_state};"
                f"commission_api_proof_state={commission_api_proof_state};"
                f"fba_fee_api_proof_state={fba_fee_api_proof_state};"
                f"other_fee_api_proof_state={other_fee_api_proof_state};"
                f"shipping_income_api_proof_state={shipping_income_api_proof_state};"
                f"shipping_fee_api_proof_state={shipping_fee_api_proof_state};"
                f"roi_money_confidence_state={roi_money_confidence_state};"
                f"refund_proof_state={refund_proof_state};"
                f"fee_shipping_proof_state={fee_shipping_proof_state};"
                f"roi_refund_proof_state={roi_refund_proof_state};"
                f"bridge_values_safe_for_live_roi={live_roi_safe}"
            ),
            source_path=str(summary_path),
            summary="Refund, shipping fee, and ROI support should be labelled as API proved, Sellerboard bridge estimate, or not yet proven.",
            root_cause_guess="Refund/fee/ROI linkage is not yet fully API-proven." if refund_fee_status != "ok" else "",
            manager_action=(
                "Keep this as a labelled bridge-gap warning until API allocation is available. "
                "Do not feed Sellerboard values into live ROI without Luke."
            ),
            safe_repair_boundary="Read-only bridge gap reporting only; no live ROI change, data correction, local DB alignment, Sheet write, or price change.",
        ),
    ]


def _b_refund_fee_shipping_gap_review_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    review_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv"
    required_columns = [
        "money_area",
        "manager_money_label",
        "source_metric",
        "source_value",
        "api_proof_state",
        "sellerboard_witness_rows",
        "gap_rows",
        "downstream_warning_rows",
        "live_roi_use_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
        "source_path",
    ]
    if not review_path.exists():
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_refund_fee_shipping_gap_review",
                status="not_checked",
                severity="info",
                value="not_yet_proven",
                producer="scripts.flows.B.B067_build_refund_fee_shipping_gap_review",
                expected_output="out/systems/B/refunds/b_refund_fee_shipping_gap_review.csv",
                actual_proof="refund_fee_shipping_gap_review_not_built",
                source_path=str(review_path),
                summary="B refund, fee, shipping, ROI, and restock money confidence must be labelled from outside the loop.",
                root_cause_guess="The read-only B067 money gap review has not been built yet.",
                manager_action="Build the read-only B067 refund fee shipping gap review, then rerun B MOT.",
                safe_repair_boundary="Read-only B money gap proof only; no B run/restart, Sheet write, local DB alignment, output deletion, ROI use, price change, queue edit, or data correction.",
            )
        ]

    headers = csv_headers(review_path) or []
    missing_schema = [column for column in required_columns if column not in headers]
    review_rows = read_csv_rows(review_path)
    summary_rows = read_csv_rows(summary_path)
    metric_rows = {row.get("metric", ""): row for row in summary_rows}
    allowed_labels = {"api_proved", "sellerboard_bridge_estimate", "not_yet_proven"}
    unclassified = [
        row.get("money_area", "")
        for row in review_rows
        if row.get("manager_money_label", "") not in allowed_labels
    ]
    unsafe_rows = [
        row.get("money_area", "")
        for row in review_rows
        if row.get("live_roi_use_allowed", "") != "0"
        or row.get("roi_or_restock_use_allowed", "") != "0"
        or row.get("sellerboard_final_truth_allowed", "") != "0"
    ]
    api_proved = sum(1 for row in review_rows if row.get("manager_money_label", "") == "api_proved")
    bridge_estimate = sum(1 for row in review_rows if row.get("manager_money_label", "") == "sellerboard_bridge_estimate")
    not_yet = sum(1 for row in review_rows if row.get("manager_money_label", "") == "not_yet_proven")
    live_roi_safe = _summary_metric(metric_rows, "bridge_values_safe_for_live_roi") or ("1" if not bridge_estimate and not not_yet else "0")
    b_source_api_proved = _summary_metric_int(metric_rows, "b_source_api_proved_rows")
    b_source_bridge_estimate = _summary_metric_int(metric_rows, "b_source_sellerboard_bridge_estimate_rows")
    b_source_not_yet = _summary_metric_int(metric_rows, "b_source_not_yet_proven_rows")
    b_source_handoff_ready = (_summary_metric(metric_rows, "b_source_handoff_ready") or "0") == "1"
    downstream_consumer_warnings = _summary_metric_int(metric_rows, "downstream_consumer_warning_rows")
    e_downstream = _summary_metric_int(metric_rows, "e_downstream_warning_rows")
    o_downstream = _summary_metric_int(metric_rows, "o_downstream_warning_rows")

    if missing_schema or unsafe_rows or unclassified:
        status = "fail"
    elif b_source_bridge_estimate or b_source_not_yet or not b_source_handoff_ready:
        status = "warn"
    else:
        status = "ok"

    root = ""
    action = "Keep this proof under MOT. Do not use bridge values as final ROI or restocking truth."
    if status == "fail":
        root = "B067 money gap proof is missing required columns, contains unclassified labels, or has unsafe live-use flags."
        action = "Repair the read-only proof mapping only. Do not change refund, fee, shipping, ROI, restock, token, order, Sheet, or DB data."
    elif status == "warn":
        root = "Some B refund, fee, or shipping source evidence is still bridge-labelled or not API-proven."
        action = (
            "Keep the B source gap visible and create bounded API proof tasks where needed. "
            "Do not feed Sellerboard estimates into live ROI/restocking."
        )
    elif downstream_consumer_warnings or e_downstream or o_downstream or live_roi_safe != "1":
        root = ""
        action = (
            "B source money proof is ready for handoff. Keep downstream E/O confidence warnings visible "
            "until those flows consume the proof; do not treat that as a B source failure."
        )

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_refund_fee_shipping_gap_review",
            status=status,
            severity=_severity(status),
            value=(
                f"b_source_api_proved={b_source_api_proved};"
                f"b_source_bridge_estimate={b_source_bridge_estimate};"
                f"b_source_not_yet_proven={b_source_not_yet};"
                f"b_source_handoff_ready={1 if b_source_handoff_ready else 0};"
                f"downstream_consumer_warnings={downstream_consumer_warnings}"
            ),
            producer="scripts.flows.B.B067_build_refund_fee_shipping_gap_review",
            expected_output="out/systems/B/refunds/b_refund_fee_shipping_gap_review.csv",
            actual_proof=(
                f"rows={len(review_rows)};missing_schema={';'.join(missing_schema)};"
                f"unclassified={';'.join(unclassified[:10])};unsafe={';'.join(unsafe_rows[:10])};"
                f"api_proved={api_proved};sellerboard_bridge_estimate={bridge_estimate};"
                f"not_yet_proven={not_yet};bridge_values_safe_for_live_roi={live_roi_safe};"
                f"b_source_api_proved={b_source_api_proved};"
                f"b_source_sellerboard_bridge_estimate={b_source_bridge_estimate};"
                f"b_source_not_yet_proven={b_source_not_yet};"
                f"b_source_handoff_ready={1 if b_source_handoff_ready else 0};"
                f"downstream_consumer_warning_rows={downstream_consumer_warnings};"
                f"e_downstream_warning_rows={e_downstream};o_downstream_warning_rows={o_downstream}"
            ),
            row_count=str(len(review_rows)),
            source_path=f"{review_path};{summary_path}",
            summary="B money confidence must separate B API source proof from downstream E/O consumer warnings.",
            root_cause_guess=root,
            manager_action=action,
            safe_repair_boundary="Read-only B067 money gap proof only; no B run/restart, Sheet write, local DB alignment, output deletion, live ROI/restock use, Sellerboard-final truth, price change, queue edit, or data correction.",
        )
    ]


def _b_level3_fee_shipping_api_proof_map_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    proof_path = base / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv"
    summary_path = base / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map_summary.csv"
    required_columns = [
        "money_field",
        "api_source_file",
        "source_amount_types",
        "source_row_count",
        "official_output_file",
        "official_output_field",
        "official_output_row_count",
        "order_master_row_count",
        "required_keys_present",
        "missing_required_keys",
        "proof_label",
        "proof_reason",
        "live_roi_use_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    if not proof_path.exists():
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_level3_fee_shipping_api_proof_map",
                status="not_checked",
                severity="info",
                value="not_yet_proven",
                producer="scripts.flows.B.B068_build_level3_fee_shipping_api_proof_map",
                expected_output="out/systems/B/refunds/b_level3_fee_shipping_api_proof_map.csv",
                actual_proof="level3_fee_shipping_api_proof_map_not_built",
                source_path=str(proof_path),
                summary="B should prove fee and shipping source availability from existing Level 3 API-backed financial events before ROI/restocking trust them.",
                root_cause_guess="The read-only B068 Level 3 fee/shipping proof map has not been built yet.",
                manager_action="Build the read-only B068 proof map, then rerun B MOT.",
                safe_repair_boundary="Read-only B Level 3 fee/shipping proof map only; no live API pull, B run/restart, Sheet write, local DB alignment, output deletion, ROI/restock use, price change, queue edit, or data correction.",
            )
        ]

    headers = csv_headers(proof_path) or []
    missing_schema = [column for column in required_columns if column not in headers]
    proof_rows = read_csv_rows(proof_path)
    summary_rows = read_csv_rows(summary_path)
    metric_rows = {row.get("metric", ""): row for row in summary_rows}
    labels = {
        "api_source_available",
        "api_source_missing",
        "repo_path_unclear",
        "protected_live_pull_required",
        "superseded_non_blocking",
    }
    unclassified = [row.get("money_field", "") for row in proof_rows if row.get("proof_label", "") not in labels]
    unsafe = [
        row.get("money_field", "")
        for row in proof_rows
        if row.get("live_roi_use_allowed", "") != "0"
        or row.get("roi_or_restock_use_allowed", "") != "0"
        or row.get("sellerboard_final_truth_allowed", "") != "0"
    ]
    api_available = sum(1 for row in proof_rows if row.get("proof_label", "") == "api_source_available")
    api_missing = sum(1 for row in proof_rows if row.get("proof_label", "") == "api_source_missing")
    repo_unclear = sum(1 for row in proof_rows if row.get("proof_label", "") == "repo_path_unclear")
    protected_pull = sum(1 for row in proof_rows if row.get("proof_label", "") == "protected_live_pull_required")
    superseded_non_blocking = sum(1 for row in proof_rows if row.get("proof_label", "") == "superseded_non_blocking")
    level3_raw_rows = _summary_metric_int(metric_rows, "level3_raw_rows")
    level3_official_rows = _summary_metric_int(metric_rows, "level3_official_rows")

    if missing_schema or unclassified or unsafe:
        status = "fail"
    elif api_missing or repo_unclear or protected_pull:
        status = "warn"
    else:
        status = "ok"

    root = ""
    action = "Keep this proof under MOT and keep B067 blocking weak values until downstream confidence is updated."
    if status == "fail":
        root = "B068 proof map is missing required columns, contains unrecognised labels, or allows unsafe live use."
        action = "Repair the read-only proof map only. Do not change fee/shipping, ROI, restock, order, token, Sheet, or DB data."
    elif status == "warn":
        root = "Some fee/shipping fields are still source-missing, repo-path-unclear, or would require a protected live pull."
        action = (
            "Keep source-missing or unclear fields warning-labelled. Do not use available raw source rows in live ROI/restocking "
            "until a separate official-output mapping is approved and proved."
        )

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_level3_fee_shipping_api_proof_map",
            status=status,
            severity=_severity(status),
            value=(
                f"api_source_available={api_available};repo_path_unclear={repo_unclear};"
                f"api_source_missing={api_missing};protected_live_pull={protected_pull};"
                f"superseded_non_blocking={superseded_non_blocking}"
            ),
            producer="scripts.flows.B.B068_build_level3_fee_shipping_api_proof_map",
            expected_output="out/systems/B/refunds/b_level3_fee_shipping_api_proof_map.csv",
            actual_proof=(
                f"rows={len(proof_rows)};missing_schema={';'.join(missing_schema)};"
                f"unclassified={';'.join(unclassified[:10])};unsafe={';'.join(unsafe[:10])};"
                f"api_source_available={api_available};repo_path_unclear={repo_unclear};"
                f"api_source_missing={api_missing};protected_live_pull_required={protected_pull};"
                f"superseded_non_blocking={superseded_non_blocking};"
                f"level3_raw_rows={level3_raw_rows};level3_official_rows={level3_official_rows}"
            ),
            row_count=str(len(proof_rows)),
            source_path=f"{proof_path};{summary_path}",
            summary="B Level 3 fee/shipping proof map should show which money fields already have API-backed local source rows and which remain missing or unclear.",
            root_cause_guess=root,
            manager_action=action,
            safe_repair_boundary="Read-only B068 Level 3 fee/shipping proof map only; no live Amazon API pull, B run/restart, Sheet write, local DB alignment, output deletion, live ROI/restock use, price change, queue edit, Sellerboard-final truth, or data correction.",
        )
    ]


def _b_sellerboard_email_intake_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    output_dir = base / "out" / "systems" / "M" / SELLERBOARD_EMAIL_INTAKE_DIR_NAME
    summary_path = output_dir / SELLERBOARD_EMAIL_INTAKE_SUMMARY_CSV_NAME
    try:
        result = build_sellerboard_email_intake_report(root=base, observed_utc=observed_utc)
    except Exception as exc:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_sellerboard_email_intake",
                status="fail",
                severity="blocker",
                value=f"build_failed:{exc.__class__.__name__}",
                producer="sellerone_manager.sellerboard_email_intake",
                expected_output=f"out/systems/M/{SELLERBOARD_EMAIL_INTAKE_DIR_NAME}/{SELLERBOARD_EMAIL_INTAKE_SUMMARY_CSV_NAME}",
                actual_proof=f"build_failed:{exc.__class__.__name__}",
                source_path=str(summary_path),
                summary="Sellerboard email intake proof should build from the local attachment intake area.",
                root_cause_guess="The manager email intake report could not be built.",
                manager_action="Repair the manager email intake report only. Do not delete attachments or change Gmail from MOT.",
                safe_repair_boundary="Sellerboard email intake manager reporting only; no Gmail deletion, local output deletion, B run, Sheet write, local DB alignment, price change, or queue edit.",
            )
        ]

    metric_rows = {row.get("metric", ""): row for row in result.summary_rows}
    source_visible = _summary_metric_int(metric_rows, "source_mailbox_visible")
    local_oauth_present = _summary_metric_int(metric_rows, "local_gmail_oauth_files_present")
    source_access_method = _summary_metric(metric_rows, "source_access_method") or "local_gmail_oauth"
    source_auth_status = _summary_metric(metric_rows, "source_auth_status")
    auth_needs_luke = (not local_oauth_present) or source_auth_status in {
        "oauth_not_valid",
        "missing_oauth_files",
        "token_unreadable",
        "oauth_refresh_failed",
    }
    expected_mailbox = _summary_metric(metric_rows, "expected_source_mailbox") or "admin@drjselect.co.uk"
    source_status = _summary_metric(metric_rows, "source_mailbox_status") or "fail"
    attachment_present = _summary_metric_int(metric_rows, "latest_attachment_present")
    required_missing = _summary_metric_int(metric_rows, "required_columns_missing")
    cleanup_count = _summary_metric_int(metric_rows, "cleanup_candidate_count")
    cleanup_allowed = _summary_metric_int(metric_rows, "cleanup_delete_allowed_count")
    cleanup_bytes = _summary_metric_int(metric_rows, "cleanup_candidate_bytes")
    latest_age_status = str(metric_rows.get("latest_attachment_age_hours", {}).get("status", "not_checked"))

    admin_access_status = "ok" if source_visible else "decision_needed" if auth_needs_luke else "fail"
    attachment_status = "ok" if attachment_present else "fail" if source_visible else "not_checked"
    format_status = "fail" if required_missing else "ok" if attachment_present and source_visible else "not_checked"
    freshness_status = "warn" if latest_age_status == "warn" and source_visible else "ok" if attachment_present and source_visible else "not_checked"
    cleanup_status = "ok" if cleanup_allowed == cleanup_count else "decision_needed" if cleanup_count else "ok"

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_email_admin_inbox_access",
            status=admin_access_status,
            severity=_severity(admin_access_status),
            value=(
                f"method={source_access_method};expected_mailbox={expected_mailbox};"
                f"local_oauth_present={local_oauth_present};auth_status={source_auth_status};"
                f"source_mailbox_visible={source_visible};source_status={source_status}"
            ),
            producer="sellerone_manager.sellerboard_email_intake",
            expected_output="Local Gmail source proof can see the Sellerboard label and latest message in admin@drjselect.co.uk",
            actual_proof=(
                f"source_access_method={source_access_method};local_gmail_oauth_files_present={local_oauth_present};"
                f"source_auth_status={source_auth_status};"
                f"source_mailbox_visible={source_visible};"
                f"source_latest_message_seen={_summary_metric(metric_rows, 'source_latest_message_seen')};"
                f"source_latest_attachment_filename={_summary_metric(metric_rows, 'source_latest_attachment_filename')}"
            ),
            source_path=str(summary_path),
            summary="The Sellerboard email intake is not proved until local Gmail source proof sees the admin inbox source message and attachment metadata.",
            root_cause_guess=(
                "Local Gmail OAuth is missing or invalid for the admin Sellerboard inbox."
                if not source_visible and auth_needs_luke
                else "Local Gmail OAuth exists, but the Sellerboard label and attachment metadata are not yet proved."
                if not source_visible
                else ""
            ),
            manager_action=(
                f"Luke must connect or re-authorize local Gmail access for {expected_mailbox} before this email intake can be manager-proven."
                if not source_visible and auth_needs_luke
                else "Create a bounded read-only local Gmail source-proof task. Do not download attachments or delete Gmail."
                if not source_visible
                else "No manager action unless the daily attachment stops arriving."
            ),
            luke_action_required="1" if not source_visible and auth_needs_luke else "0",
            safe_repair_boundary=(
                "Sellerboard email source proof only; Gmail source authorization decision if OAuth is missing; "
                "no attachment download, no Gmail deletion, local output deletion, B run, restart, "
                "Sheet write, local DB alignment, price change, queue edit, or ROI use."
            ),
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_email_attachment_arrived",
            status=attachment_status,
            severity=_severity(attachment_status),
            value=f"latest_attachment_present={attachment_present}",
            producer="sellerone_manager.sellerboard_email_intake",
            expected_output="daily Sellerboard OrderList CSV in manager intake folder",
            actual_proof=f"latest_attachment_present={attachment_present}",
            row_count=str(len(result.attachment_rows)),
            source_path=str(summary_path),
            summary="The daily Sellerboard email attachment must arrive before the bridge can compare Sellerboard to B.",
            root_cause_guess=(
                "Local Gmail source proof is not complete yet, so attachment arrival cannot be judged."
                if not source_visible
                else "No Sellerboard OrderList attachment has been saved into the manager intake area."
                if not attachment_present
                else ""
            ),
            manager_action=(
                f"First connect or re-authorize local Gmail access for {expected_mailbox}; then retest attachment arrival."
                if not source_visible and auth_needs_luke
                else "First build read-only local Gmail source proof; then retest attachment arrival."
                if not source_visible
                else "Create a bounded B email-intake task to save the Sellerboard attachment. Do not delete email or local files from MOT."
            ),
            safe_repair_boundary="Sellerboard email intake connection and report only; no Gmail deletion, local output deletion, B run, restart, Sheet write, local DB alignment, price change, or queue edit.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_email_attachment_format",
            status=format_status,
            severity=_severity(format_status),
            value=f"required_columns_missing={required_missing}",
            producer="sellerone_manager.sellerboard_email_intake",
            expected_output="Sellerboard OrderList attachment has expected columns",
            actual_proof=f"required_columns_missing={required_missing}",
            row_count=str(len(result.attachment_rows)),
            source_path=str(summary_path),
            summary="Sellerboard attachment format must match the bridge parser before it is used as outside proof.",
            root_cause_guess="Sellerboard attachment columns are missing or the daily email has not arrived." if format_status == "fail" else "",
            manager_action="Create a bounded format task if the first daily email differs from the manual sample.",
            safe_repair_boundary="Sellerboard email format/parser report only; no B run, Sheet write, local DB alignment, output deletion, or business data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_email_attachment_freshness",
            status=freshness_status,
            severity=_severity(freshness_status),
            value=str(metric_rows.get("latest_attachment_age_hours", {}).get("value", "")),
            producer="sellerone_manager.sellerboard_email_intake",
            expected_output="daily Sellerboard attachment is fresh enough for MOT comparison",
            actual_proof=f"latest_attachment_age_hours={metric_rows.get('latest_attachment_age_hours', {}).get('value', '')}",
            row_count=str(len(result.attachment_rows)),
            source_path=str(summary_path),
            summary="Sellerboard daily proof should be fresh enough to catch missing orders quickly.",
            root_cause_guess="Sellerboard attachment is stale." if freshness_status == "warn" else "",
            manager_action="Keep as an MOT warning until the next email arrives; do not run B or repair business data from this row.",
            safe_repair_boundary="Sellerboard email freshness proof only; no B run, Sheet write, local DB alignment, output deletion, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_sellerboard_email_storage_cleanup_guard",
            status=cleanup_status,
            severity=_severity(cleanup_status),
            value=f"cleanup_candidates={cleanup_count};delete_allowed={cleanup_allowed};candidate_bytes={cleanup_bytes}",
            producer="sellerone_manager.sellerboard_email_intake",
            expected_output="cleanup candidates are listed but not deleted without Luke approval",
            actual_proof=f"cleanup_candidate_count={cleanup_count};cleanup_delete_allowed_count={cleanup_allowed};cleanup_candidate_bytes={cleanup_bytes}",
            row_count=str(len(result.cleanup_rows)),
            source_path=str(summary_path),
            summary="Sellerboard intake storage should stay lean, but deletion must be explicit and guarded.",
            root_cause_guess="Sellerboard intake has cleanup candidates that are not approved by the narrow local cleanup policy." if cleanup_status == "decision_needed" else "",
            manager_action="Apply only the approved local cleanup policy. Stop for Luke before deleting Gmail, business outputs, non-OrderList files, or files outside the intake folder.",
            luke_action_required="1" if cleanup_status == "decision_needed" else "0",
            safe_repair_boundary="Approved local Sellerboard intake cleanup only; no Gmail deletion, no business output deletion, no non-OrderList deletion, no B run, and no data correction.",
        ),
    ]


def _summary_metric(metric_rows: dict[str, dict[str, str]], metric: str) -> str:
    return metric_rows.get(metric, {}).get("value", "")


def _summary_metric_int(metric_rows: dict[str, dict[str, str]], metric: str) -> int:
    try:
        return int(float(_summary_metric(metric_rows, metric) or "0"))
    except ValueError:
        return 0


def _money_review_label(review_rows: list[dict[str, str]], money_area: str) -> str:
    for row in review_rows:
        if _mot_text(row.get("money_area", "")) == money_area:
            return (
                _mot_text(row.get("manager_money_label", ""))
                or _mot_text(row.get("api_proof_state", ""))
                or "not_reported"
            )
    return "not_reported"


def _money_review_metric(metric_rows: dict[str, dict[str, str]], metric: str) -> str:
    return _summary_metric(metric_rows, metric) or "0"


def _b_marketplace_coverage_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    output_dir = base / "out" / "systems" / "M" / B_MARKETPLACE_COVERAGE_DIR_NAME
    coverage_path = output_dir / B_MARKETPLACE_COVERAGE_CSV_NAME
    summary_path = output_dir / B_MARKETPLACE_SUMMARY_CSV_NAME
    try:
        result = build_b_marketplace_coverage_report(root=base, observed_utc=observed_utc)
        write_b_marketplace_coverage_outputs(result, base / "out" / "systems" / "M")
    except Exception as exc:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_marketplace_coverage_report",
                status="fail",
                severity="blocker",
                value=f"build_failed:{exc.__class__.__name__}",
                producer="sellerone_manager.b_marketplace_coverage",
                expected_output=f"out/systems/M/{B_MARKETPLACE_COVERAGE_DIR_NAME}/{B_MARKETPLACE_COVERAGE_CSV_NAME}",
                actual_proof=f"build_failed:{exc.__class__.__name__}",
                source_path=str(coverage_path),
                summary="B marketplace coverage proof should build read-only from local order and Sellerboard evidence.",
                root_cause_guess="The manager coverage report could not be built.",
                manager_action="Repair the manager marketplace coverage report only. Do not run B or correct order data.",
                safe_repair_boundary="B marketplace coverage manager reporting only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, or data correction.",
            )
        ]

    metric_rows = {row.get("metric", ""): row for row in result.summary_rows}
    missing_shipped = _summary_metric_int(metric_rows, "sellerboard_missing_shipped_orders")
    fail_rows = _summary_metric_int(metric_rows, "marketplace_fail_rows")
    warn_rows = _summary_metric_int(metric_rows, "marketplace_warn_rows")
    status_diff_warn_rows = _summary_metric_int(metric_rows, "marketplace_status_difference_warn_rows")
    warn_notes = metric_rows.get("marketplace_warn_rows", {}).get("notes", "")
    cursor_risk = _summary_metric_int(metric_rows, "shared_cursor_risk_rows")
    participating = _summary_metric_int(metric_rows, "participating_marketplaces")
    sellerboard_markets = _summary_metric_int(metric_rows, "sellerboard_marketplaces")
    local_markets = _summary_metric_int(metric_rows, "local_order_marketplaces")

    report_status = result.status
    report_value = (
        f"participating={participating};local_markets={local_markets};"
        f"sellerboard_markets={sellerboard_markets};fail_rows={fail_rows};warn_rows={warn_rows};"
        f"status_diff_warn_rows={status_diff_warn_rows}"
    )
    gap_status = "fail" if missing_shipped or fail_rows else "ok"
    cursor_status = "fail" if cursor_risk else "ok"
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_marketplace_coverage_report",
            status=report_status,
            severity=_severity(report_status),
            value=report_value,
            producer="sellerone_manager.b_marketplace_coverage",
            expected_output=f"out/systems/M/{B_MARKETPLACE_COVERAGE_DIR_NAME}/{B_MARKETPLACE_COVERAGE_CSV_NAME}",
            actual_proof=report_value + (f";warn_labels={warn_notes}" if warn_notes else ""),
            row_count=str(len(result.coverage_rows)),
            source_path=str(coverage_path),
            summary="B must prove marketplace coverage independently, not just fresh UK order output.",
            root_cause_guess=(
                "One or more marketplaces are not proven by independent Sellerboard/local evidence."
                if report_status == "fail"
                else "Marketplace coverage is warning-labelled, but no missing shipped order or shared cursor risk is active."
                if report_status == "warn"
                else ""
            ),
            manager_action=(
                "Keep the warning visible and compare only the labelled marketplace rows. Do not run B, backfill, or correct data from MOT."
                if report_status == "warn"
                else "Create a bounded B manager task for marketplace coverage proof. Do not run B, backfill, or correct data from MOT."
            ),
            safe_repair_boundary="B marketplace coverage reporting and proof design only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_marketplace_sellerboard_gaps",
            status=gap_status,
            severity=_severity(gap_status),
            value=f"sellerboard_missing_shipped_orders={missing_shipped};marketplace_fail_rows={fail_rows}",
            producer="sellerone_manager.b_marketplace_coverage",
            expected_output="Sellerboard marketplace activity matched to local B marketplace proof",
            actual_proof=f"sellerboard_missing_shipped_orders={missing_shipped};marketplace_fail_rows={fail_rows}",
            source_path=str(summary_path),
            summary="Sellerboard marketplace activity should not reveal shipped orders missing from local B proof.",
            root_cause_guess="Sellerboard has marketplace activity that local B proof does not cover." if gap_status == "fail" else "",
            manager_action="Create a bounded B marketplace-coverage task. Do not recover or backfill orders without Luke approval.",
            safe_repair_boundary="B marketplace coverage diagnosis only; no B run, no backfill, no marker edit, no Sheet write, no local DB alignment, no output deletion, and no data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_marketplace_shared_cursor_risk",
            status=cursor_status,
            severity=_severity(cursor_status),
            value=f"shared_cursor_risk_rows={cursor_risk}",
            producer="sellerone_manager.b_marketplace_coverage",
            expected_output="per-marketplace order coverage proof",
            actual_proof=f"shared_cursor_risk_rows={cursor_risk}",
            source_path=str(summary_path),
            summary="A fresh UK/global order marker must not hide older or quieter non-UK marketplace orders.",
            root_cause_guess="The shared B order cursor may have advanced past missing non-UK marketplace activity." if cursor_status == "fail" else "",
            manager_action="Design per-marketplace coverage proof before any recovery. Do not edit markers from MOT.",
            safe_repair_boundary="B marketplace cursor-risk proof only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.",
        ),
    ]


def _b_order_recovery_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    output_dir = base / "out" / "systems" / "M" / B_ORDER_RECOVERY_DIR_NAME
    plan_path = output_dir / B_ORDER_RECOVERY_PLAN_CSV_NAME
    summary_path = output_dir / B_ORDER_RECOVERY_SUMMARY_CSV_NAME
    try:
        result = build_b_order_recovery_plan(root=base, observed_utc=observed_utc)
        write_b_order_recovery_outputs(result, base / "out" / "systems" / "M")
    except Exception as exc:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_backdate_recovery_plan",
                status="fail",
                severity="blocker",
                value=f"build_failed:{exc.__class__.__name__}",
                producer="sellerone_manager.b_order_recovery",
                expected_output=f"out/systems/M/{B_ORDER_RECOVERY_DIR_NAME}/{B_ORDER_RECOVERY_PLAN_CSV_NAME}",
                actual_proof=f"build_failed:{exc.__class__.__name__}",
                source_path=str(plan_path),
                summary="B backdate recovery control should build read-only from local order, Sellerboard, cursor, and quarantine evidence.",
                root_cause_guess="The manager recovery plan report could not be built.",
                manager_action="Repair the manager recovery report only. Do not run B, backfill, edit markers, or correct order data.",
                safe_repair_boundary="B recovery manager reporting only; no B run, restart, backfill, marker edit, Sheet write, local DB alignment, output deletion, or data correction.",
            )
        ]

    metric_rows = {row.get("metric", ""): row for row in result.summary_rows}
    missing_cursors = _summary_metric_int(metric_rows, "per_marketplace_cursor_missing_count")
    stale_cursors = _summary_metric_int(metric_rows, "per_marketplace_cursor_stale_count")
    sellerboard_missing = _summary_metric_int(metric_rows, "sellerboard_missing_orders")
    unrecovered_missing = _summary_metric_int(metric_rows, "unrecovered_missing_sellerboard_orders")
    quarantine_rows = _summary_metric_int(metric_rows, "quarantine_rows")
    duplicate_risk = _summary_metric_int(metric_rows, "duplicate_risk_orders")
    merge_ready = _summary_metric_int(metric_rows, "merge_ready_without_approval_orders")
    invalid_labels = _summary_metric_int(metric_rows, "invalid_quarantine_proof_label_rows")
    missing_quarantine_columns = _summary_metric_int(metric_rows, "quarantine_required_columns_missing")

    recovery_status = "fail" if unrecovered_missing else "ok"
    cursor_status = "fail" if missing_cursors or stale_cursors else "ok"
    if result.status == "not_checked" and not sellerboard_missing and not missing_cursors and not stale_cursors:
        recovery_status = "not_checked"
        cursor_status = "not_checked"
    duplicate_status = "decision_needed" if merge_ready else "fail" if duplicate_risk else "ok"
    label_status = "fail" if invalid_labels or missing_quarantine_columns else "ok" if quarantine_rows else "not_checked"

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_backdate_recovery_quarantine",
            status=recovery_status,
            severity=_severity(recovery_status),
            value=f"sellerboard_missing={sellerboard_missing};unrecovered={unrecovered_missing};quarantine_rows={quarantine_rows}",
            producer="sellerone_manager.b_order_recovery",
            expected_output="Sellerboard missing shipped orders are API-proved in recovery quarantine before any live merge",
            actual_proof=(
                f"sellerboard_missing_orders={sellerboard_missing};"
                f"unrecovered_missing_sellerboard_orders={unrecovered_missing};"
                f"quarantine_rows={quarantine_rows}"
            ),
            row_count=str(len(result.plan_rows)),
            source_path=str(summary_path),
            summary="Missing B orders must be recovered into quarantine proof before any live order, ROI, or restocking use.",
            root_cause_guess="Sellerboard shows shipped orders that are not API-proved in quarantine." if recovery_status == "fail" else "",
            manager_action="Create a bounded B recovery task to build the read-only backdate scanner and quarantine proof. Do not run B or merge data from MOT.",
            safe_repair_boundary="B recovery scanner and quarantine proof code only; no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, live merge, ROI use, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_future_marketplace_order_cursors",
            status=cursor_status,
            severity=_severity(cursor_status),
            value=f"missing_cursors={missing_cursors};stale_cursors={stale_cursors}",
            producer="sellerone_manager.b_order_recovery",
            expected_output="fresh per-marketplace B order cursor proof for every Amazon marketplace",
            actual_proof=f"per_marketplace_cursor_missing_count={missing_cursors};per_marketplace_cursor_stale_count={stale_cursors}",
            row_count=str(len(result.plan_rows)),
            source_path=str(plan_path),
            summary="Future B order coverage needs one fresh cursor per Amazon marketplace so UK activity cannot hide quiet marketplaces.",
            root_cause_guess="One or more Amazon marketplaces do not have fresh independent cursor proof." if cursor_status == "fail" else "",
            manager_action="Create a bounded B future-coverage task to add per-marketplace cursor proof. Do not edit the shared marker from MOT.",
            safe_repair_boundary="B per-marketplace cursor proof code only; no marker edit, B run, backfill, restart, Sheet write, local DB alignment, output deletion, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_recovery_duplicate_and_merge_guard",
            status=duplicate_status,
            severity=_severity(duplicate_status),
            value=f"duplicate_risk={duplicate_risk};merge_ready_without_approval={merge_ready}",
            producer="sellerone_manager.b_order_recovery",
            expected_output="recovered orders remain quarantined, deduped, and not live-merge ready without Luke",
            actual_proof=f"duplicate_risk_orders={duplicate_risk};merge_ready_without_approval_orders={merge_ready}",
            row_count=str(len(result.plan_rows)),
            source_path=str(summary_path),
            summary="Recovered orders must not duplicate existing orders or become live-merge ready before approval.",
            root_cause_guess=(
                "Recovered order data appears to cross a protected merge boundary." if merge_ready else
                "Recovered order quarantine has duplicate risk." if duplicate_risk else ""
            ),
            manager_action="Stop for Luke if live merge is involved. Otherwise create a bounded duplicate-guard repair task.",
            luke_action_required="1" if merge_ready else "0",
            safe_repair_boundary="B quarantine duplicate guard only; no live merge, local DB alignment, Sheet write, output deletion, B run, restart, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_recovery_proof_labels",
            status=label_status,
            severity=_severity(label_status),
            value=f"invalid_labels={invalid_labels};missing_quarantine_columns={missing_quarantine_columns};quarantine_rows={quarantine_rows}",
            producer="sellerone_manager.b_order_recovery",
            expected_output="recovery quarantine labels each value as API proved, Sellerboard bridge estimate, or not yet proven",
            actual_proof=(
                f"invalid_quarantine_proof_label_rows={invalid_labels};"
                f"quarantine_required_columns_missing={missing_quarantine_columns};"
                f"quarantine_rows={quarantine_rows}"
            ),
            row_count=str(len(result.plan_rows)),
            source_path=str(summary_path),
            summary="Recovery proof labels must stop Sellerboard estimates being mistaken for final API truth.",
            root_cause_guess="Recovery quarantine proof labels or required columns are missing." if label_status == "fail" else "",
            manager_action="Repair only the recovery proof schema or label contract. Do not alter live business data.",
            safe_repair_boundary="B recovery proof schema and labels only; no B run, live merge, Sheet write, local DB alignment, output deletion, ROI use, or data correction.",
        ),
    ]


def _b_order_promotion_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    output_dir = base / "out" / "systems" / "M" / B_ORDER_PROMOTION_DIR_NAME
    preview_path = output_dir / B_ORDER_PROMOTION_PREVIEW_CSV_NAME
    manifest_path = base / "out" / "systems" / "B" / "order_promotion" / B_ORDER_PROMOTION_MANIFEST_JSON_NAME
    try:
        result = build_b_order_promotion_plan(root=base, observed_utc=observed_utc)
    except Exception as exc:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="B",
                check="b_order_promotion_preview",
                status="fail",
                severity="blocker",
                value=f"build_failed:{exc.__class__.__name__}",
                producer="sellerone_manager.b_order_promotion",
                expected_output=f"out/systems/M/{B_ORDER_PROMOTION_DIR_NAME}/{B_ORDER_PROMOTION_PREVIEW_CSV_NAME}",
                actual_proof=f"build_failed:{exc.__class__.__name__}",
                source_path=str(preview_path),
                summary="B recovered orders need a protected promotion preview before any live local output merge.",
                root_cause_guess="The manager order promotion preview could not be built.",
                manager_action="Repair the manager promotion preview only. Do not promote, run B, write Sheets, or sync DB from MOT.",
                safe_repair_boundary="B promotion preview reporting only; no live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
            )
        ]

    metric_rows = {row.get("metric", ""): row for row in result.summary_rows}
    api_orders = _summary_metric_int(metric_rows, "api_proved_quarantine_orders")
    ready_orders = _summary_metric_int(metric_rows, "promotion_ready_orders")
    blocked_orders = _summary_metric_int(metric_rows, "promotion_blocked_orders")
    already_live = _summary_metric_int(metric_rows, "already_live_orders")
    manifest_status = _summary_metric(metric_rows, "latest_promotion_manifest_status")

    if blocked_orders:
        preview_status = "fail"
        preview_value = f"blocked={blocked_orders}"
        preview_root = "One or more API-proved recovered orders are missing fields or have duplicate risk before promotion."
        preview_action = "Create a bounded B promotion-proof repair task. Do not promote live outputs until the preview clears."
        preview_luke = "0"
    elif ready_orders:
        preview_status = "decision_needed"
        preview_value = f"ready_pending_approval={ready_orders}"
        preview_root = "Recovered orders are ready for live local promotion, which is a protected action."
        preview_action = "Luke must approve the protected B order promotion repair window before Codex can write live B outputs."
        preview_luke = "1"
    else:
        preview_status = "ok"
        preview_value = f"api_quarantine_orders={api_orders};already_live={already_live}"
        preview_root = ""
        preview_action = "No promotion action needed unless a new API-proved quarantine order appears."
        preview_luke = "0"

    if blocked_orders:
        live_status = "fail"
        live_value = "promotion_blocked"
        live_root = "Promotion cannot safely rebuild the live B order chain yet."
        live_action = "Repair the promotion preview proof first. Do not write live order outputs."
        live_luke = "0"
    elif ready_orders:
        live_status = "decision_needed"
        live_value = "awaiting_luke_promotion_approval"
        live_root = "The final live order-chain repair is protected."
        live_action = "Stop for Luke before writing orders, order items, Level 1, Order Master, or SQL shadow tables."
        live_luke = "1"
    elif api_orders and already_live and manifest_status != "promoted":
        live_status = "warn"
        live_value = "live_without_promotion_manifest"
        live_root = "Recovered order appears live, but the protected promotion manifest is not the proof source."
        live_action = "Keep visible until a clean promotion manifest or normal B API catch-up proof explains the live row."
        live_luke = "0"
    else:
        live_status = "ok"
        live_value = f"manifest={manifest_status or 'not_required'};already_live={already_live}"
        live_root = ""
        live_action = "Keep final promotion proof under B MOT."
        live_luke = "0"

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_order_promotion_preview",
            status=preview_status,
            severity=_severity(preview_status),
            value=preview_value,
            producer="sellerone_manager.b_order_promotion",
            expected_output="API-proved quarantine rows validate as promotion-ready before live local merge",
            actual_proof=f"api_proved_quarantine_orders={api_orders};promotion_ready_orders={ready_orders};promotion_blocked_orders={blocked_orders};already_live_orders={already_live}",
            row_count=str(len(result.preview_rows)),
            source_path=str(preview_path),
            summary="Recovered B orders must pass a promotion preview before they can be written into live local order outputs.",
            root_cause_guess=preview_root,
            manager_action=preview_action,
            luke_action_required=preview_luke,
            safe_repair_boundary="B promotion preview and proof only; no live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_order_promotion_live_chain",
            status=live_status,
            severity=_severity(live_status),
            value=live_value,
            producer="sellerone_manager.b_order_promotion",
            expected_output="promoted recovered orders appear in live B orders, items, Level 1, Order Master, SQL shadow, and MOT proof",
            actual_proof=f"manifest_status={manifest_status};promotion_ready_orders={ready_orders};promotion_blocked_orders={blocked_orders};already_live_orders={already_live}",
            row_count=str(len(result.preview_rows)),
            source_path=str(manifest_path),
            summary="B is fully repaired only when API-proved recovered orders are promoted through the real local B chain or there is no promotion needed.",
            root_cause_guess=live_root,
            manager_action=live_action,
            luke_action_required=live_luke,
            safe_repair_boundary="B live promotion proof only; stop before live promotion, B run, restart, Sheet write, DB sync, output deletion, ROI use, price change, queue edit, or data correction.",
        ),
    ]


def _b_old_checklist_clue_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    checklist_path = base / "out" / "cycle_alerts" / "checklist_B.csv"
    split_path = base / "out" / "cycle_alerts" / "checklist_B_split.csv"
    rows = read_csv_rows(split_path) or read_csv_rows(checklist_path)
    fail_count = sum(1 for row in rows if row.get("status", "").strip().lower() in {"fail", "failed", "blocked"})
    warn_count = sum(1 for row in rows if row.get("status", "").strip().lower() in {"warn", "warning", "stale_evidence"})
    source = split_path if split_path.exists() else checklist_path
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_old_checklist_clue",
            status="not_checked",
            severity="info",
            value=f"fail={fail_count};warn={warn_count};rows={len(rows)}",
            producer="A015_build_system_health_check.py",
            expected_output="out/cycle_alerts/checklist_B*.csv",
            actual_proof=f"old_checklist_fail={fail_count};old_checklist_warn={warn_count};rows={len(rows)}",
            row_count=str(len(rows)),
            source_path=str(source),
            summary="The old B checklist is a clue only. It is not the manager's proof that B is healthy.",
            manager_action="Use this as triage context only. Manager truth comes from outside B MOT proof rows.",
            safe_repair_boundary="Classification clue only; do not repair B from this row alone.",
        )
    ]


B_CORE_MAINTENANCE_CHECKS = [
    "b_latest_manifest",
    "b_orders_all",
    "b_order_items_all",
    "b_order_master",
    "b_token_ledger_live",
    "b_token_cogs_ledger",
    "b_token_shortages_by_sku",
    "b_pnl_daily",
    "b_stock_snapshot_latest",
    "b_parked_skus",
    "b_worker_owner",
    "b_supervisor_owner",
    "b_maintenance_marker_state",
]

B_EMAIL_MAINTENANCE_CHECKS = [
    "b_sellerboard_email_admin_inbox_access",
    "b_sellerboard_email_attachment_arrived",
    "b_sellerboard_email_attachment_format",
    "b_sellerboard_email_storage_cleanup_guard",
]

B_CURSOR_MAINTENANCE_CHECKS = [
    "b_future_marketplace_order_cursors",
    "b_marketplace_shared_cursor_risk",
]

B_RECOVERY_CONTROL_CHECKS = [
    "b_backdate_recovery_quarantine",
    "b_order_promotion_preview",
    "b_recovery_duplicate_and_merge_guard",
    "b_recovery_proof_labels",
]

B_ORDER_TRUTH_CHECKS = [
    "b_sellerboard_bridge_report",
    "b_sellerboard_bridge_schema",
    "b_sellerboard_order_reconciliation",
    "b_fallback_token_cost_audit",
    "b_fallback_cost_proof_reconciliation",
    "b_refund_return_token_bridge",
    "b_return_cogs_residual_review",
    "b_return_token_repair_preview",
    "b_refund_token_reproof_preview",
    "b_original_return_status_conflict_preview",
    "b_original_return_status_apply_preview",
    "b_disposition_conflict_preview",
    "b_disposition_conflict_decision_preview",
    "b_disposition_correction_impact_preview",
    "b_disposition_correction_apply_preview",
    "b_historical_replacement_stock_proof",
    "b_no_replacement_shortage_exception_review",
    "b_disposition_correction_swap_apply",
    "b_sellerboard_refund_fee_roi_bridge",
    "b_refund_fee_shipping_gap_review",
    "b_level3_fee_shipping_api_proof_map",
    "b_stock_receipt_token_sync",
    "b_marketplace_coverage_report",
    "b_marketplace_sellerboard_gaps",
    "b_marketplace_shared_cursor_risk",
    "b_backdate_recovery_quarantine",
    "b_order_promotion_preview",
    "b_order_promotion_live_chain",
    "b_future_marketplace_order_cursors",
    "b_recovery_duplicate_and_merge_guard",
    "b_recovery_proof_labels",
]


def _b_completion_gate_rows(*, rows: list[dict[str, str]], observed_utc: str) -> list[dict[str, str]]:
    by_check = {row.get("check", ""): row for row in rows}
    protected_decisions = [
        check
        for check, row in by_check.items()
        if str(row.get("flow", "")).upper() == "B"
        and (row.get("status") == "decision_needed" or row.get("luke_action_required") == "1")
    ]
    core_failures = _checks_with_status(by_check, B_CORE_MAINTENANCE_CHECKS, {"fail"})
    email_failures = _checks_with_status(by_check, B_EMAIL_MAINTENANCE_CHECKS, {"fail"})
    email_not_proven = _checks_with_status(by_check, B_EMAIL_MAINTENANCE_CHECKS, {"not_checked"})
    cursor_failures = _checks_with_status(by_check, B_CURSOR_MAINTENANCE_CHECKS, {"fail"})
    recovery_controls_missing = _checks_with_status(by_check, B_RECOVERY_CONTROL_CHECKS, {"missing_check"})
    recovery_controls_active = len(recovery_controls_missing) == 0
    visible_order_truth_failures = [
        check
        for check in [
            "b_sellerboard_order_reconciliation",
            "b_marketplace_sellerboard_gaps",
            "b_backdate_recovery_quarantine",
        ]
        if by_check.get(check, {}).get("status") == "fail"
    ]
    visible_order_truth_warnings = [
        check
        for check in [
            "b_sellerboard_order_reconciliation",
            "b_marketplace_sellerboard_gaps",
            "b_backdate_recovery_quarantine",
        ]
        if by_check.get(check, {}).get("status") == "warn"
    ]
    bridge_warns = _checks_with_status(
        by_check,
        ["b_sellerboard_refund_fee_roi_bridge", "b_refund_return_token_bridge"],
        {"warn"},
    )

    hard_failures = sorted(
        set(
            core_failures
            + email_failures
            + email_not_proven
            + cursor_failures
            + recovery_controls_missing
            + visible_order_truth_failures
        )
    )
    if protected_decisions:
        management_status = "decision_needed"
        management_value = "blocked_by_luke_decision"
        management_root = "A protected decision is needed before B Management can be called ready."
        if "b_sellerboard_email_admin_inbox_access" in protected_decisions:
            management_action = "Luke must connect or re-authorize local Gmail OAuth access for admin@drjselect.co.uk before B Management can be called ready."
        else:
            management_action = "Handle the protected B decision first. Do not run B, delete Gmail, edit markers, write Sheets, align the DB, or feed bridge data into ROI."
        luke_required = "1"
    elif hard_failures:
        management_status = "fail"
        management_value = "not_ready"
        management_root = "One or more B management readiness proofs are missing or failing."
        management_action = "Create or continue bounded B manager tasks for the failed readiness checks. Prove each fix with the same B MOT row clearing."
        luke_required = "0"
    else:
        management_status = "ok"
        if visible_order_truth_warnings or bridge_warns:
            management_value = "ready_for_maintenance_with_parked_truth_warnings"
        else:
            management_value = "ready_for_maintenance"
        management_root = "B is maintainable, but order truth is still not complete."
        management_action = "B can be watched by the manager, but keep recovery and Sellerboard bridge gaps visible until API proof clears them."
        luke_required = "0"

    order_truth_decisions = _checks_with_status(by_check, B_ORDER_TRUTH_CHECKS, {"decision_needed"})
    order_truth_failures = _checks_with_status(by_check, B_ORDER_TRUTH_CHECKS, {"fail"})
    order_truth_warnings = _checks_with_status(by_check, B_ORDER_TRUTH_CHECKS, {"warn"})
    order_truth_missing = _checks_with_status(by_check, B_ORDER_TRUTH_CHECKS, {"missing_check"})
    order_truth_not_checked = [
        check
        for check in _checks_with_status(by_check, B_ORDER_TRUTH_CHECKS, {"not_checked"})
        if check != "b_recovery_proof_labels"
    ]
    if order_truth_decisions:
        truth_status = "decision_needed"
        truth_value = "blocked_by_protected_decision"
        truth_root = "A protected decision is needed before order truth can be completed."
        truth_action = "Stop for Luke before any protected merge, Gmail, Sheet, DB, output deletion, ROI, price, queue, or B runtime action."
        truth_luke = "1"
    elif order_truth_failures:
        truth_status = "fail"
        truth_value = "not_complete"
        truth_root = "B order truth still has missing orders, marketplace gaps, cursor gaps, or quarantine gaps."
        truth_action = "Continue bounded B recovery, marketplace cursor, and Sellerboard comparison tasks. Do not use recovered or bridge values in live ROI."
        truth_luke = "0"
    elif order_truth_warnings:
        truth_status = "warn"
        truth_value = "bridge_gaps_visible"
        truth_root = "Refund, fee, shipping, or ROI bridge proof is still not fully API-proven."
        truth_action = "Keep Sellerboard bridge values labelled and separate until direct API proof is available."
        truth_luke = "0"
    elif order_truth_missing or order_truth_not_checked:
        truth_status = "not_checked"
        truth_value = "not_yet_proven"
        truth_root = "Order truth completion checks are not all active yet."
        truth_action = "Activate the missing B order truth proof rows before calling B complete."
        truth_luke = "0"
    else:
        truth_status = "ok"
        truth_value = "complete"
        truth_root = ""
        truth_action = "Keep Sellerboard as a cross-check and keep direct API proof as the source of truth."
        truth_luke = "0"

    source_path = ";".join(
        row.get("source_path", "")
        for row in rows
        if row.get("flow") == "B" and row.get("source_path")
    )
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_management_ready_for_maintenance",
            status=management_status,
            severity=_severity(management_status),
            value=(
                f"{management_value};hard_failures={len(hard_failures)};"
                f"protected_decisions={len(protected_decisions)};"
                f"visible_order_truth_gaps={len(visible_order_truth_failures) + len(visible_order_truth_warnings)};"
                f"recovery_controls_active={1 if recovery_controls_active else 0}"
            ),
            producer="sellerone_manager.hourly_mot",
            expected_output="B Management readiness gate",
            actual_proof=(
                f"hard_failures={';'.join(hard_failures)};"
                f"protected_decisions={';'.join(protected_decisions)};"
                f"visible_order_truth_gaps={';'.join(visible_order_truth_failures + visible_order_truth_warnings)};"
                f"bridge_warns={';'.join(bridge_warns)}"
            ),
            source_path=source_path,
            summary="B Management is ready only when independent proof can watch B, protect recovery, and keep known order gaps visible.",
            root_cause_guess=management_root,
            manager_action=management_action,
            luke_action_required=luke_required,
            safe_repair_boundary="B manager readiness proof only; no B run, restart, Gmail deletion, marker edit, Sheet write, local DB alignment, output deletion, ROI use, price change, queue edit, or data correction.",
        ),
        mot_row(
            observed_utc=observed_utc,
            flow="B",
            check="b_order_truth_completion",
            status=truth_status,
            severity=_severity(truth_status),
            value=(
                f"{truth_value};failures={len(order_truth_failures)};"
                f"warnings={len(order_truth_warnings)};"
                f"not_checked={len(order_truth_not_checked) + len(order_truth_missing)}"
            ),
            producer="sellerone_manager.hourly_mot",
            expected_output="B order truth completion gate",
            actual_proof=(
                f"failures={';'.join(order_truth_failures)};"
                f"warnings={';'.join(order_truth_warnings)};"
                f"decisions={';'.join(order_truth_decisions)};"
                f"not_checked={';'.join(order_truth_not_checked + order_truth_missing)}"
            ),
            source_path=source_path,
            summary="B order truth is complete only when marketplace, Sellerboard, recovery, refund, shipping, fee, and ROI proof is API-proven or clearly labelled.",
            root_cause_guess=truth_root,
            manager_action=truth_action,
            luke_action_required=truth_luke,
            safe_repair_boundary="B order truth proof only; no live merge, B run, restart, Sheet write, local DB alignment, output deletion, ROI use, price change, queue edit, or data correction.",
        ),
    ]


def _checks_with_status(
    by_check: dict[str, dict[str, str]],
    checks: list[str],
    statuses: set[str],
) -> list[str]:
    out: list[str] = []
    for check in checks:
        row = by_check.get(check)
        status = row.get("status", "") if row else "missing_check"
        if status in statuses:
            out.append(check)
    return out


def _manifest_step_names(manifest: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        return out
    for step in steps:
        if not isinstance(step, dict):
            continue
        name = str(step.get("name", "") or "").strip()
        script = str(step.get("script_or_function", "") or "").strip()
        if name:
            out.add(name)
        if script:
            out.add(script)
    return out


def _manifest_step(manifest: dict[str, Any], expected_name: str) -> dict[str, Any]:
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        return {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        names = {
            str(step.get("name", "") or "").strip(),
            str(step.get("script_or_function", "") or "").strip(),
        }
        if expected_name in names:
            return step
    return {}


def _e_manifest_rows(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    manifest: dict[str, Any],
    manifest_path: Path | None,
) -> list[dict[str, str]]:
    if not manifest_path:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="E",
                check="e_latest_manifest",
                status="fail",
                severity="blocker",
                value="missing",
                producer="scripts/cycles/run_E_cycle.py",
                expected_output="out/manifests/E/**/*.json",
                actual_proof="manifest_missing",
                source_path=str(base / "out" / "manifests" / "E"),
                summary="No E manifest was found, so the manager cannot prove E completed from outside evidence.",
                root_cause_guess="E has no durable run proof.",
                manager_action="Create a bounded E proof-writing task before trusting E analytics state.",
                safe_repair_boundary="E runner proof only; do not run E unless Luke approves an E-owned proof window.",
            )
        ]

    end_time = parse_utc(str(manifest.get("end_time", "")))
    age = max((now - end_time).total_seconds() / 3600.0, 0.0) if end_time else file_age_hours(manifest_path, now)
    final_state = str(manifest.get("final_state", "") or "unknown")
    status = status_from_age(age, warn_hours=E_DAILY_WARN_HOURS, fail_hours=E_DAILY_FAIL_HOURS)
    missing_steps = [step for step in E_EXPECTED_STEPS if step not in _manifest_step_names(manifest)]
    root_cause = ""
    value = final_state
    if final_state not in {"completed", "success"}:
        status = "fail"
        root_cause = "E manifest did not reach a completed state."
    elif missing_steps:
        status = "fail"
        value = "missing_steps"
        root_cause = "E manifest is missing one or more expected E steps."
    elif status != "ok":
        root_cause = "E manifest is stale."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_latest_manifest",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="out/manifests/E/**/*.json",
            actual_proof=(
                f"manifest_age_hours={_age_text(age)};final_state={final_state};"
                f"missing_steps={','.join(missing_steps)}"
            ),
            age_hours=_age_text(age),
            source_path=str(manifest_path),
            summary="Latest E manifest proves whether E reached the end of its analytics sequence.",
            root_cause_guess=root_cause,
            manager_action="If fail, create a bounded E runner proof task. Do not repair downstream reports to hide it.",
            safe_repair_boundary="E runner proof and manifest traversal only; no E live run without approval.",
        )
    ]


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        return []
    return rows


def _e_run_log_rows(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    log_paths = [base / "out" / "systems" / "E" / "live" / "e_run_log.jsonl", base / "out" / "e_run_log.jsonl"]
    all_rows: list[tuple[Path, dict[str, Any]]] = []
    for path in log_paths:
        all_rows.extend((path, row) for row in _jsonl_rows(path))
    successes = [
        (path, row)
        for path, row in all_rows
        if str(row.get("status", "") or "").strip().lower() == "success"
    ]
    if not successes:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="E",
                check="e_run_log_success",
                status="fail",
                severity="blocker",
                value="missing_success",
                producer="scripts/cycles/run_E_cycle.py",
                expected_output="out/systems/E/live/e_run_log.jsonl",
                actual_proof="no_success_row_found",
                source_path=";".join(str(path) for path in log_paths),
                summary="E should leave a recent successful run-log row that matches the latest E manifest.",
                root_cause_guess="No successful E run-log row was found.",
                manager_action="Create a bounded E run-log proof task before trusting E output freshness.",
                safe_repair_boundary="E run-log proof only; no E live run without approval.",
            )
        ]

    def _success_time(item: tuple[Path, dict[str, Any]]) -> datetime:
        row = item[1]
        return parse_utc(str(row.get("finished_utc", "") or row.get("started_utc", ""))) or datetime.min.replace(tzinfo=timezone.utc)

    source_path, latest_success = max(successes, key=_success_time)
    finished = parse_utc(str(latest_success.get("finished_utc", "") or latest_success.get("started_utc", "")))
    age = max((now - finished).total_seconds() / 3600.0, 0.0) if finished else None
    status = status_from_age(age, warn_hours=E_DAILY_WARN_HOURS, fail_hours=E_DAILY_FAIL_HOURS)
    run_id = str(latest_success.get("run_id", "") or "").strip()
    manifest_run_id = str(manifest.get("run_id", "") or "").strip()
    root_cause = ""
    value = "success"
    if not run_id:
        status = "fail"
        value = "missing_run_id"
        root_cause = "Latest successful E run-log row has no run id."
    elif manifest_run_id and run_id != manifest_run_id:
        status = "fail"
        value = "manifest_mismatch"
        root_cause = "Latest successful E run-log row does not match the latest E manifest run id."
    elif status != "ok":
        root_cause = "Latest successful E run-log row is stale."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_run_log_success",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="out/systems/E/live/e_run_log.jsonl",
            actual_proof=(
                f"run_id={run_id};manifest_run_id={manifest_run_id};"
                f"finished_utc={latest_success.get('finished_utc', '')};age_hours={_age_text(age)};"
                f"output_asof={latest_success.get('output_asof', '')}"
            ),
            age_hours=_age_text(age),
            source_path=str(source_path),
            summary="E run log should show a recent successful analytics run tied to the latest manifest.",
            root_cause_guess=root_cause,
            manager_action="If fail, package E run-log or runner proof repair. Do not run E from MOT.",
            safe_repair_boundary="E run-log proof only; no E live run without approval.",
        )
    ]


def _row_time(row: dict[str, Any]) -> datetime:
    return parse_utc(str(row.get("finished_utc", "") or row.get("started_utc", ""))) or datetime.min.replace(tzinfo=timezone.utc)


def _e_cadence_control_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    log_paths = [base / "out" / "systems" / "E" / "live" / "e_run_log.jsonl", base / "out" / "e_run_log.jsonl"]
    all_rows: list[tuple[Path, dict[str, Any]]] = []
    for path in log_paths:
        all_rows.extend((path, row) for row in _jsonl_rows(path))
    if not all_rows:
        return [
            mot_row(
                observed_utc=observed_utc,
                flow="E",
                check="e_cadence_control",
                status="not_checked",
                severity="info",
                value="waiting_for_run_log",
                producer="scripts/cycles/run_E_cycle.py",
                expected_output="recent E success or cadence skip/run proof in e_run_log.jsonl",
                actual_proof="no_run_log_rows_found",
                source_path=";".join(str(path) for path in log_paths),
                summary="E cadence proof should show a recent successful run and preserve skip/run decisions in the run log.",
                root_cause_guess="Cadence proof waits until the E run log can be read.",
                manager_action="Use the E run-log proof row first; do not run E from MOT.",
                safe_repair_boundary="E cadence proof only; no E live run, publish enablement, Sheet write, local DB alignment, or output deletion.",
            )
        ]

    successes = [
        (path, row)
        for path, row in all_rows
        if str(row.get("status", "") or "").strip().lower() == "success"
    ]
    skipped = [
        (path, row)
        for path, row in all_rows
        if str(row.get("status", "") or "").strip().lower() == "skipped_cadence"
    ]
    latest_path, latest_row = max(all_rows, key=lambda item: _row_time(item[1]))
    latest_status = str(latest_row.get("status", "") or "").strip().lower()
    latest_success: tuple[Path, dict[str, Any]] | None = max(successes, key=lambda item: _row_time(item[1])) if successes else None
    age: float | None = None

    if latest_success is None:
        status = "fail"
        value = "missing_success"
        root_cause = "E run log has rows, but no successful E analytics run is recorded."
        source_path = str(latest_path)
    else:
        success_path, success_row = latest_success
        success_time = _row_time(success_row)
        age = max((now - success_time).total_seconds() / 3600.0, 0.0) if success_time.year > 1 else None
        freshness = status_from_age(age, warn_hours=E_DAILY_WARN_HOURS, fail_hours=E_DAILY_FAIL_HOURS)
        source_path = str(success_path)
        if freshness == "fail":
            status = "fail"
            value = "latest_success_stale"
            root_cause = "Latest successful E cadence proof is too old."
        elif freshness == "warn":
            status = "warn"
            value = "latest_success_old"
            root_cause = "Latest successful E cadence proof is getting old."
        else:
            status = "ok"
            value = "cadence_run_proved"
            root_cause = ""

    latest_success_row = latest_success[1] if latest_success is not None else {}
    proof = (
        f"latest_status={latest_status};success_rows={len(successes)};skipped_cadence_rows={len(skipped)};"
        f"last_success_age_hours={_age_text(age)};"
        f"expected_input_asof={latest_success_row.get('expected_input_asof', '')};"
        f"output_asof={latest_success_row.get('output_asof', '')};"
        f"asof_rerun_trigger={latest_success_row.get('asof_rerun_trigger', '')}"
    )
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_cadence_control",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="recent E success or cadence skip/run proof in e_run_log.jsonl",
            actual_proof=proof,
            age_hours=_age_text(age),
            source_path=source_path,
            summary="E cadence proof should show a recent successful run and preserve skip/run decisions in the run log.",
            root_cause_guess=root_cause,
            manager_action=(
                "If fail, package an E cadence or run-log proof task. Do not run E from MOT."
                if status == "fail"
                else "No manager action needed for E cadence proof."
            ),
            safe_repair_boundary="E cadence proof only; no E live run, publish enablement, Sheet write, local DB alignment, or output deletion.",
        )
    ]


def _e_input_readiness_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    problems: list[str] = []
    warnings: list[str] = []
    first_path = ""
    first_producer = "scripts/cycles/run_E_cycle.py"
    proof_parts: list[str] = []
    for item in E_INPUT_PROOFS:
        path = base / str(item["path"])
        rows_count = csv_row_count(path)
        age = file_age_hours(path, now)
        name = str(item["name"])
        min_rows = int(item.get("min_rows", 0) or 0)
        proof_parts.append(f"{name}:rows={'' if rows_count is None else rows_count},age={_age_text(age)}")
        if rows_count is None:
            problems.append(f"{name}:missing_or_unreadable")
        elif rows_count < min_rows:
            problems.append(f"{name}:rows_below_min:{rows_count}<{min_rows}")
        else:
            freshness = status_from_age(
                age,
                warn_hours=float(item.get("warn_hours", E_DAILY_WARN_HOURS)),
                fail_hours=float(item.get("fail_hours", E_DAILY_FAIL_HOURS)),
            )
            if freshness == "fail":
                problems.append(f"{name}:stale")
            elif freshness == "warn":
                warnings.append(f"{name}:old")
        if (problems or warnings) and not first_path:
            first_path = str(path)
            first_producer = str(item.get("producer", "scripts/cycles/run_E_cycle.py"))

    if problems:
        status = "fail"
        value = problems[0]
        root_cause = "An ingredient E needs for clean analytics is missing, empty, unreadable, or too stale."
        manager_action = "Create a bounded input-readiness repair task for that producer. Do not make downstream reports look clean."
    elif warnings:
        status = "warn"
        value = warnings[0]
        root_cause = "An E input exists but is getting old enough to weaken confidence."
        manager_action = "Keep E under MOT watch; if the age crosses fail threshold, package a producer-specific repair."
    else:
        status = "ok"
        value = "inputs_ready"
        root_cause = ""
        manager_action = "No manager action needed for E input readiness."

    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_input_readiness",
            status=status,
            severity=_severity(status),
            value=value,
            producer=first_producer,
            expected_output="fresh order, inventory, COGS, FX, fee, listing, and refund inputs",
            actual_proof=";".join(proof_parts),
            source_path=first_path or ";".join(str(base / str(item["path"])) for item in E_INPUT_PROOFS),
            summary="E should say whether its source ingredients are fresh enough before the business report is trusted.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="E input-readiness proof only; no Google Sheets write, local DB alignment, output deletion, or E live run.",
        )
    ]


def _e_output_state(base: Path, now: datetime) -> dict[str, dict[str, object]]:
    states: dict[str, dict[str, object]] = {}
    for item in E_CORE_OUTPUTS:
        path = base / str(item["path"])
        states[str(item["name"])] = {
            "item": item,
            "path": path,
            "age": file_age_hours(path, now),
            "rows": csv_row_count(path),
            "headers": csv_headers(path),
        }
    return states


def _e_core_outputs_fresh_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    states = _e_output_state(base, now)
    issues: list[str] = []
    stale: list[str] = []
    first_producer = "scripts/cycles/run_E_cycle.py"
    first_path = ""
    for name, state in states.items():
        item = state["item"]
        path = state["path"]
        rows_count = state["rows"]
        age = state["age"]
        min_rows = int(item.get("min_rows", 0) or 0)  # type: ignore[union-attr]
        if rows_count is None:
            issues.append(f"{name}:missing_or_unreadable")
        elif int(rows_count) < min_rows:
            issues.append(f"{name}:rows_below_min:{rows_count}<{min_rows}")
        else:
            freshness = status_from_age(age if isinstance(age, float) else None, warn_hours=E_DAILY_WARN_HOURS, fail_hours=E_DAILY_FAIL_HOURS)
            if freshness == "fail":
                issues.append(f"{name}:stale")
            elif freshness == "warn":
                stale.append(f"{name}:old")
        if (issues or stale) and not first_path:
            first_producer = str(item.get("producer", "scripts/cycles/run_E_cycle.py"))  # type: ignore[union-attr]
            first_path = str(path)

    if issues:
        status = "fail"
        value = issues[0]
        root_cause = "One or more required E outputs is missing, empty, unreadable, or too stale."
        manager_action = "Create a producer-specific E repair task for the first failed output. Do not patch downstream reports."
    elif stale:
        status = "warn"
        value = stale[0]
        root_cause = "One or more required E outputs is getting old."
        manager_action = "Keep E under MOT watch; create a task only if it crosses the fail threshold."
    else:
        status = "ok"
        value = "fresh_enough"
        root_cause = ""
        manager_action = "No manager action needed for required E output freshness."
    proof = ";".join(
        f"{name}:rows={state['rows'] if state['rows'] is not None else ''},age={_age_text(state['age'] if isinstance(state['age'], float) else None)}"
        for name, state in states.items()
    )
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_core_outputs_fresh",
            status=status,
            severity=_severity(status),
            value=value,
            producer=first_producer,
            expected_output=";".join(str(item["path"]) for item in E_CORE_OUTPUTS),
            actual_proof=proof,
            source_path=first_path or ";".join(str(base / str(item["path"])) for item in E_CORE_OUTPUTS),
            summary="Required E analytics outputs should exist, have rows, and be fresh enough for E.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="E producer output proof only; no E live run, Sheet write, local DB alignment, or downstream masking.",
        )
    ]


def _e_core_row_count_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    counts = {
        str(item["name"]): csv_row_count(base / str(item["path"]))
        for item in E_CORE_OUTPUTS
    }
    if any(value is None for value in counts.values()):
        status = "not_checked"
        value = "waiting_for_outputs"
        root_cause = "Row-count proof waits until every required E output can be read."
    else:
        problems: list[str] = []
        perf = int(counts["performance_summary"] or 0)
        restock = int(counts["restock_signals"] or 0)
        study = int(counts["study_report"] or 0)
        roi = int(counts["roi_snapshot"] or 0)
        truth = int(counts["sales_truth_sku_30d"] or 0)
        recon = int(counts["sales_truth_reconciliation"] or 0)
        velocity = int(counts["sales_velocity"] or 0)
        daily = int(counts["sku_daily_sales_truth"] or 0)
        for item in E_CORE_OUTPUTS:
            name = str(item["name"])
            min_rows = int(item.get("min_rows", 0) or 0)
            if int(counts[name] or 0) < min_rows:
                problems.append(f"{name}:rows_below_min")
        if perf != restock or perf != study:
            problems.append("performance_restock_study_row_counts_differ")
        if roi != truth or roi != recon:
            problems.append("roi_truth_reconciliation_row_counts_differ")
        if velocity < perf:
            problems.append("velocity_rows_below_performance_rows")
        if daily < roi:
            problems.append("daily_truth_rows_below_roi_rows")
        status = "fail" if problems else "ok"
        value = problems[0] if problems else "believable"
        root_cause = "E row counts do not line up across the analytics outputs." if problems else ""
    proof = ";".join(f"{name}={'' if value is None else value}" for name, value in counts.items())
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_core_row_counts_believable",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="believable row counts across E outputs",
            actual_proof=proof,
            row_count=proof,
            source_path=";".join(str(base / str(item["path"])) for item in E_CORE_OUTPUTS),
            summary="E output row counts should look like the same SKU universe, not random leftovers.",
            root_cause_guess=root_cause,
            manager_action="If fail, create an E row-count or producer-contract task before trusting the analytics.",
            safe_repair_boundary="E row-count proof only; no output deletion, local DB alignment, or downstream masking.",
        )
    ]


def _e_schema_contract_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    missing_files: list[str] = []
    missing_columns: list[str] = []
    first_path = ""
    for item in E_CORE_OUTPUTS:
        path = base / str(item["path"])
        headers = csv_headers(path)
        if headers is None:
            missing_files.append(str(item["name"]))
            continue
        missing = [column for column in item["columns"] if column not in headers]  # type: ignore[index]
        if missing:
            missing_columns.append(f"{item['name']}:{','.join(missing)}")
            if not first_path:
                first_path = str(path)
    if missing_columns:
        status = "fail"
        value = missing_columns[0]
        root_cause = "A required E output exists but does not match the expected column contract."
        manager_action = "Create an E output-contract repair task for the producer that wrote the bad schema."
    elif missing_files:
        status = "not_checked"
        value = "waiting_for_outputs"
        root_cause = "Schema proof waits until every required E output can be read."
        manager_action = "Use the missing-output MOT row as the repair source, not the schema row."
    else:
        status = "ok"
        value = "contracts_ok"
        root_cause = ""
        manager_action = "No manager action needed for E output schemas."
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_schema_contracts",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="required columns in every core E output",
            actual_proof=f"missing_files={','.join(missing_files)};missing_columns={';'.join(missing_columns)}",
            source_path=first_path or ";".join(str(base / str(item["path"])) for item in E_CORE_OUTPUTS),
            summary="Every required E output should keep its expected columns.",
            root_cause_guess=root_cause,
            manager_action=manager_action,
            safe_repair_boundary="E schema contract only; no Sheet writes, local DB alignment, or downstream masking.",
        )
    ]


def _to_float(value: object) -> float:
    try:
        text = str(value or "").strip()
        if not text:
            return 0.0
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def _is_blankish(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "nan", "none", "null"}


def _sku_set(rows: list[dict[str, str]] | None) -> set[str]:
    if rows is None:
        return set()
    return {str(row.get("sku", "") or "").strip() for row in rows if str(row.get("sku", "") or "").strip()}


def _e_cross_output_alignment_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    paths = {str(item["name"]): base / str(item["path"]) for item in E_CORE_OUTPUTS}
    required_names = [
        "roi_snapshot",
        "restock_signals",
        "performance_summary",
        "study_report",
        "sales_truth_sku_30d",
        "sales_truth_reconciliation",
    ]
    data = {name: read_csv_dicts(paths[name]) for name in required_names}
    if any(data[name] is None for name in required_names):
        status = "not_checked"
        value = "waiting_for_outputs"
        root_cause = "Alignment proof waits until required E outputs can be read."
    else:
        problems: list[str] = []
        perf_rows = data["performance_summary"] or []
        restock_rows = data["restock_signals"] or []
        study_rows = data["study_report"] or []
        roi_rows = data["roi_snapshot"] or []
        truth_rows = data["sales_truth_sku_30d"] or []
        recon_rows = data["sales_truth_reconciliation"] or []
        perf_skus = _sku_set(perf_rows)
        restock_skus = _sku_set(restock_rows)
        study_skus = _sku_set(study_rows)
        roi_skus = _sku_set(roi_rows)
        truth_skus = _sku_set(truth_rows)
        recon_skus = _sku_set(recon_rows)
        if perf_skus != restock_skus:
            problems.append("performance_restock_sku_set_mismatch")
        if perf_skus != study_skus:
            problems.append("performance_study_sku_set_mismatch")
        if not roi_skus.issubset(perf_skus):
            problems.append("roi_skus_missing_from_performance")
        if roi_skus != truth_skus or roi_skus != recon_skus:
            problems.append("roi_truth_reconciliation_sku_set_mismatch")
        delta_mismatch = 0
        for row in recon_rows:
            if (
                abs(_to_float(row.get("units_delta", ""))) > 0.0001
                or abs(_to_float(row.get("revenue_delta_gbp", ""))) > 0.01
                or abs(_to_float(row.get("profit_delta_gbp", ""))) > 0.01
            ):
                delta_mismatch += 1
        if delta_mismatch:
            problems.append(f"reconciliation_delta_rows:{delta_mismatch}")
        perf_by_sku = {str(row.get("sku", "") or "").strip(): row for row in perf_rows}
        roi_unit_mismatches = 0
        for row in roi_rows:
            sku = str(row.get("sku", "") or "").strip()
            perf = perf_by_sku.get(sku, {})
            if not perf:
                continue
            perf_units = perf.get("units_sold_roi", perf.get("units_sold", ""))
            if abs(_to_float(perf_units) - _to_float(row.get("units_sold", ""))) > 0.0001:
                roi_unit_mismatches += 1
        if roi_unit_mismatches:
            problems.append(f"roi_performance_unit_mismatch_rows:{roi_unit_mismatches}")
        status = "fail" if problems else "ok"
        value = problems[0] if problems else "aligned"
        root_cause = "E outputs disagree with each other, so the analytics proof is not trustworthy." if problems else ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_cross_output_alignment",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="matching SKU sets and zero reconciliation deltas",
            actual_proof=value,
            source_path=";".join(str(paths[name]) for name in required_names),
            summary="E performance, restock, study, ROI, and sales-truth outputs should agree with each other.",
            root_cause_guess=root_cause,
            manager_action="If fail, create a bounded E reconciliation repair task. Do not hide the mismatch downstream.",
            safe_repair_boundary="E reconciliation proof only; no local DB alignment, output deletion, or downstream masking.",
        )
    ]


def _e_confidence_coverage_rows(*, base: Path, observed_utc: str) -> list[dict[str, str]]:
    performance_path = base / "out" / "sku_performance_summary.csv"
    study_path = base / "out" / "e_study_report.csv"
    coverage_path = base / "out" / "e_coverage_summary.csv"
    perf_rows = read_csv_dicts(performance_path)
    study_rows = read_csv_dicts(study_path)
    coverage_rows = read_csv_dicts(coverage_path)
    rows: list[dict[str, str]] = []

    required_confidence = {
        "latest_price_confidence",
        "profit_confidence",
        "sales_truth_state",
        "stock_signal",
        "restock_business_ready",
        "b_money_confidence_state",
        "b_bridge_values_safe_for_live_roi",
        "restock_decision_state",
        "restock_readiness_confidence",
        "restock_missing_proof",
        "restock_evidence_role",
        "missing_reason",
        "missing_roi_reason",
        "missing_roi_reason_detail",
    }
    perf_headers = set(csv_headers(performance_path) or [])
    study_headers = set(csv_headers(study_path) or [])
    missing_perf = sorted(required_confidence - perf_headers)
    missing_study = sorted(required_confidence - study_headers)
    if perf_rows is None or study_rows is None:
        confidence_status = "not_checked"
        confidence_value = "waiting_for_outputs"
        confidence_root = "Confidence-field proof waits until E summary and study outputs can be read."
    elif missing_perf or missing_study:
        confidence_status = "warn"
        confidence_value = "missing_confidence_fields"
        confidence_root = "Latest live E outputs do not yet contain the new confidence labels."
    else:
        confidence_status = "ok"
        confidence_value = "confidence_fields_present"
        confidence_root = ""
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_confidence_fields_live",
            status=confidence_status,
            severity=_severity(confidence_status),
            value=confidence_value,
            producer="E004_build_performance_summary.py;E005_build_study_report.py",
            expected_output="profit_confidence;sales_truth_state;stock_signal;restock_business_ready;missing_reason",
            actual_proof=f"performance_missing={','.join(missing_perf)};study_missing={','.join(missing_study)}",
            source_path=f"{performance_path};{study_path}",
            summary="E summary and study rows should show plain confidence labels instead of silent blanks.",
            root_cause_guess=confidence_root,
            manager_action="If still missing after the next approved E run, create an E output-contract repair task.",
            safe_repair_boundary="E confidence output proof only; no E live run without approval.",
        )
    )

    missing_roi_required = {"missing_roi_reason", "missing_roi_reason_detail", "profit_confidence", "restock_business_ready"}
    missing_roi_perf_cols = sorted(missing_roi_required - perf_headers)
    missing_roi_study_cols = sorted({"missing_roi_reason", "missing_roi_reason_detail"} - study_headers)
    if perf_rows is None or study_rows is None:
        missing_roi_status = "not_checked"
        missing_roi_value = "waiting_for_outputs"
        missing_roi_root = "Missing-ROI reason proof waits until E performance and study outputs can be read."
        missing_roi_actual = "waiting_for_outputs"
    elif missing_roi_perf_cols or missing_roi_study_cols:
        missing_roi_status = "warn"
        missing_roi_value = "missing_roi_reason_fields_not_live_yet"
        missing_roi_root = "Latest live E outputs do not yet contain the missing-ROI reason labels."
        missing_roi_actual = (
            f"performance_missing={','.join(missing_roi_perf_cols)};"
            f"study_missing={','.join(missing_roi_study_cols)}"
        )
    else:
        perf_by_sku = {
            str(row.get("sku", "") or "").strip(): row
            for row in perf_rows
            if str(row.get("sku", "") or "").strip()
        }
        study_by_sku = {
            str(row.get("sku", "") or "").strip(): row
            for row in study_rows
            if str(row.get("sku", "") or "").strip()
        }
        allowed_reasons = {
            "roi_clean",
            "velocity_only_sales_truth",
            "stock_only_no_sales_window",
            "no_recent_sales_truth",
            "missing_cogs_or_fx",
            "missing_fee_proof",
            "missing_refund_proof",
            "missing_current_price_proof",
            "b_money_bridge_labelled",
            "not_available",
        }
        missing_reason_allowed = allowed_reasons - {"roi_clean"}
        blank_or_bad_reason = [
            sku for sku, row in perf_by_sku.items()
            if str(row.get("profit_confidence", "") or "").strip().lower() != "profit_clean"
            and str(row.get("missing_roi_reason", "") or "").strip().lower() not in missing_reason_allowed
        ]
        ready_without_roi = [
            sku for sku, row in perf_by_sku.items()
            if str(row.get("restock_business_ready", "") or "").strip().lower() == "yes"
            and str(row.get("missing_roi_reason", "") or "").strip().lower() != "roi_clean"
        ]
        study_mismatches = [
            sku for sku, row in perf_by_sku.items()
            if sku in study_by_sku
            and str(row.get("missing_roi_reason", "") or "").strip().lower()
            != str(study_by_sku[sku].get("missing_roi_reason", "") or "").strip().lower()
        ]
        coverage_reason_cols = {f"missing_roi_reason_{label}_skus" for label in allowed_reasons}
        coverage_headers = set(csv_headers(coverage_path) or [])
        missing_coverage_reason_cols = sorted(coverage_reason_cols - coverage_headers)
        problems: list[str] = []
        if blank_or_bad_reason:
            problems.append(f"missing_reason_rows={len(blank_or_bad_reason)}")
        if ready_without_roi:
            problems.append(f"restock_ready_missing_roi_rows={len(ready_without_roi)}")
        if study_mismatches:
            problems.append(f"study_reason_mismatch_rows={len(study_mismatches)}")
        if problems:
            missing_roi_status = "fail"
            missing_roi_value = ";".join(problems)
            missing_roi_root = "E has SKU rows where missing ROI is not explained cleanly."
        elif missing_coverage_reason_cols:
            missing_roi_status = "warn"
            missing_roi_value = f"coverage_reason_counts_not_live_yet={len(missing_coverage_reason_cols)}"
            missing_roi_root = "E row-level reasons exist, but the one-row coverage summary does not yet count them."
        else:
            missing_roi_status = "ok"
            missing_roi_value = (
                "missing_roi_reason_rows="
                f"{len([row for row in perf_rows if str(row.get('missing_roi_reason', '') or '').strip().lower() != 'roi_clean'])}"
            )
            missing_roi_root = ""
        missing_roi_actual = (
            f"performance_rows={len(perf_rows)};"
            f"study_rows={len(study_rows)};"
            f"blank_or_bad_reason={len(blank_or_bad_reason)};"
            f"restock_ready_missing_roi={len(ready_without_roi)};"
            f"study_mismatches={len(study_mismatches)};"
            f"missing_coverage_reason_cols={len(missing_coverage_reason_cols)}"
        )
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_missing_roi_reasons_live",
            status=missing_roi_status,
            severity=_severity(missing_roi_status),
            value=missing_roi_value,
            producer="E004_build_performance_summary.py;E005_build_study_report.py",
            expected_output="every non-clean ROI row has missing_roi_reason and study/coverage proof carries it",
            actual_proof=missing_roi_actual,
            source_path=f"{performance_path};{study_path};{coverage_path}",
            summary="E should explain why each missing-ROI SKU is not clean business truth.",
            root_cause_guess=missing_roi_root,
            manager_action="If fail after an approved E proof run, create a bounded E missing-ROI reason repair task.",
            safe_repair_boundary="E missing-ROI reason proof only; no E live run without approval and no data correction.",
        )
    )

    restock_required = {
        "stock_signal",
        "restock_business_ready",
        "profit_confidence",
        "latest_price_confidence",
        "refund_proof_state",
        "refund_sample_confidence",
        "b_money_confidence_state",
        "b_bridge_values_safe_for_live_roi",
        "missing_roi_reason",
        "restock_decision_state",
        "restock_readiness_confidence",
        "restock_missing_proof",
        "restock_evidence_role",
    }
    restock_study_required = {
        "stock_signal",
        "restock_business_ready",
        "b_money_confidence_state",
        "b_bridge_values_safe_for_live_roi",
        "restock_decision_state",
        "restock_readiness_confidence",
        "restock_missing_proof",
        "restock_evidence_role",
    }
    restock_allowed_states = {
        "business_ready_clean",
        "stock_signal_only",
        "blocked_missing_roi",
        "blocked_missing_profit_inputs",
        "warning_bridge_labelled_money",
        "blocked_weak_refund_proof",
        "blocked_missing_current_price",
        "not_applicable_no_stock_signal",
    }
    restock_coverage_cols = {"skus_with_stock_signal"} | {
        f"restock_decision_state_{state}_skus" for state in restock_allowed_states
    } | {
        "restock_blocked_missing_roi_skus",
        "restock_blocked_weak_refund_proof_skus",
        "restock_blocked_missing_current_price_skus",
        "restock_warning_bridge_labelled_money_skus",
    }
    restock_perf_missing = sorted(restock_required - perf_headers)
    restock_study_missing = sorted(restock_study_required - study_headers)
    restock_coverage_headers = set(csv_headers(coverage_path) or [])
    restock_coverage_missing = sorted(restock_coverage_cols - restock_coverage_headers)
    if perf_rows is None or study_rows is None:
        restock_model_status = "not_checked"
        restock_model_value = "waiting_for_outputs"
        restock_model_root = "Restock-ready input model proof waits until E performance and study outputs can be read."
        restock_model_actual = "waiting_for_outputs"
    elif restock_perf_missing or restock_study_missing:
        restock_model_status = "warn"
        restock_model_value = "restock_ready_input_fields_not_live_yet"
        restock_model_root = "Latest live E outputs do not yet contain the full restock-ready input model."
        restock_model_actual = (
            f"performance_missing={','.join(restock_perf_missing)};"
            f"study_missing={','.join(restock_study_missing)};"
            f"coverage_missing={','.join(restock_coverage_missing)}"
        )
    else:
        weak_refund_states = {"", "not_yet_proven", "sellerboard_bridge_only", "bridge_labelled_only", "not_verified"}
        weak_refund_confidences = {"", "no_refund_rate_proof", "legacy_history_not_manager_proven", "not_verified"}
        price_missing_states = {"", "listing_price_unproven", "not_verified"}
        perf_by_sku = {
            str(row.get("sku", "") or "").strip(): row
            for row in perf_rows
            if str(row.get("sku", "") or "").strip()
        }
        study_by_sku = {
            str(row.get("sku", "") or "").strip(): row
            for row in study_rows
            if str(row.get("sku", "") or "").strip()
        }
        unknown_state_rows: list[str] = []
        non_ready_missing_proof: list[str] = []
        false_ready_rows: list[str] = []
        bridge_clean_rows: list[str] = []
        study_model_mismatches: list[str] = []
        state_counts = {state: 0 for state in restock_allowed_states}
        stock_signal_count = 0
        blocked_missing_roi_count = 0
        weak_refund_count = 0
        missing_price_count = 0
        bridge_warning_count = 0

        for sku, row in perf_by_sku.items():
            decision_state = _mot_text(row.get("restock_decision_state", "")).lower()
            confidence = _mot_text(row.get("restock_readiness_confidence", "")).lower()
            missing_proof = _mot_text(row.get("restock_missing_proof", "")).lower()
            ready = _mot_text(row.get("restock_business_ready", "")).lower() == "yes"
            stock_signal_seen = _mot_text(row.get("stock_signal", "")).lower() == "yes"
            profit_clean = _mot_text(row.get("profit_confidence", "")).lower() == "profit_clean"
            roi_clean = _mot_text(row.get("missing_roi_reason", "")).lower() == "roi_clean"
            price_missing = _mot_text(row.get("latest_price_confidence", "")).lower() in price_missing_states
            refund_weak = (
                _mot_text(row.get("refund_proof_state", "")).lower() in weak_refund_states
                or _mot_text(row.get("refund_sample_confidence", "")).lower() in weak_refund_confidences
            )
            b_money_safe = (
                _mot_text(row.get("b_money_confidence_state", "")).lower() == "api_backed_safe"
                and _mot_text(row.get("b_bridge_values_safe_for_live_roi", "")) == "1"
            )
            if decision_state not in restock_allowed_states:
                unknown_state_rows.append(sku)
            else:
                state_counts[decision_state] += 1
            if stock_signal_seen:
                stock_signal_count += 1
            if "missing_roi" in missing_proof:
                blocked_missing_roi_count += 1
            if "weak_refund_proof" in missing_proof:
                weak_refund_count += 1
            if "missing_current_price" in missing_proof:
                missing_price_count += 1
            if decision_state == "warning_bridge_labelled_money" or confidence == "warning":
                bridge_warning_count += 1
            if not ready and not missing_proof:
                non_ready_missing_proof.append(sku)
            if ready and (
                decision_state != "business_ready_clean"
                or confidence != "clean"
                or missing_proof
                or not stock_signal_seen
                or not profit_clean
                or not roi_clean
                or price_missing
                or refund_weak
                or not b_money_safe
            ):
                false_ready_rows.append(sku)
            if not b_money_safe and (ready or decision_state == "business_ready_clean"):
                bridge_clean_rows.append(sku)
            study = study_by_sku.get(sku)
            if study and (
                _mot_text(study.get("restock_business_ready", "")).lower() != _mot_text(row.get("restock_business_ready", "")).lower()
                or _mot_text(study.get("restock_decision_state", "")).lower() != decision_state
                or _mot_text(study.get("restock_missing_proof", "")).lower() != missing_proof
            ):
                study_model_mismatches.append(sku)

        coverage_mismatches: list[str] = []
        if coverage_rows and not restock_coverage_missing:
            coverage = coverage_rows[-1]

            def cov_int(column: str) -> int:
                try:
                    return int(float(str(coverage.get(column, "") or "0")))
                except ValueError:
                    return -1

            expected_counts = {
                "skus_with_stock_signal": stock_signal_count,
                "restock_blocked_missing_roi_skus": blocked_missing_roi_count,
                "restock_blocked_weak_refund_proof_skus": weak_refund_count,
                "restock_blocked_missing_current_price_skus": missing_price_count,
                "restock_warning_bridge_labelled_money_skus": bridge_warning_count,
            }
            expected_counts.update({f"restock_decision_state_{state}_skus": count for state, count in state_counts.items()})
            coverage_mismatches = [
                f"{column}:{cov_int(column)}!={expected}"
                for column, expected in expected_counts.items()
                if cov_int(column) != expected
            ]

        problems: list[str] = []
        if unknown_state_rows:
            problems.append(f"unknown_state_rows={len(unknown_state_rows)}")
        if non_ready_missing_proof:
            problems.append(f"non_ready_missing_proof_rows={len(non_ready_missing_proof)}")
        if false_ready_rows:
            problems.append(f"false_ready_rows={len(false_ready_rows)}")
        if bridge_clean_rows:
            problems.append(f"bridge_clean_rows={len(bridge_clean_rows)}")
        if study_model_mismatches:
            problems.append(f"study_model_mismatch_rows={len(study_model_mismatches)}")
        if coverage_mismatches:
            problems.append(f"coverage_mismatch_rows={len(coverage_mismatches)}")
        if problems:
            restock_model_status = "fail"
            restock_model_value = ";".join(problems)
            restock_model_root = "E has SKU rows where restock readiness is unsafe, incomplete, or not aligned across outputs."
        elif restock_coverage_missing:
            restock_model_status = "warn"
            restock_model_value = f"restock_coverage_counts_not_live_yet={len(restock_coverage_missing)}"
            restock_model_root = "E row-level restock model exists, but coverage summary does not yet count it."
        else:
            restock_model_status = "ok"
            restock_model_value = (
                f"stock_signal_skus={stock_signal_count};"
                f"business_ready_clean_skus={state_counts['business_ready_clean']};"
                f"warning_bridge_labelled_money_skus={state_counts['warning_bridge_labelled_money']};"
                f"blocked_missing_roi_skus={state_counts['blocked_missing_roi']};"
                f"blocked_weak_refund_proof_skus={state_counts['blocked_weak_refund_proof']};"
                f"blocked_missing_current_price_skus={state_counts['blocked_missing_current_price']}"
            )
            restock_model_root = ""
        restock_model_actual = (
            f"performance_rows={len(perf_rows)};study_rows={len(study_rows)};"
            f"unknown_state_rows={len(unknown_state_rows)};"
            f"non_ready_missing_proof_rows={len(non_ready_missing_proof)};"
            f"false_ready_rows={len(false_ready_rows)};"
            f"bridge_clean_rows={len(bridge_clean_rows)};"
            f"study_model_mismatch_rows={len(study_model_mismatches)};"
            f"coverage_missing={len(restock_coverage_missing)};"
            f"coverage_mismatch_rows={len(coverage_mismatches)}"
        )
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_restock_ready_input_model_live",
            status=restock_model_status,
            severity=_severity(restock_model_status),
            value=restock_model_value,
            producer="E004_build_performance_summary.py;E005_build_study_report.py",
            expected_output="stock_signal is separate from strict restock_business_ready, and every blocked/warning row names missing proof",
            actual_proof=restock_model_actual,
            source_path=f"{performance_path};{study_path};{coverage_path}",
            summary="E should show restock readiness as evidence only, with low stock separated from clean business-ready proof.",
            root_cause_guess=restock_model_root,
            manager_action="If fail after an approved E proof run, create a bounded E restock-ready input-model repair task.",
            safe_repair_boundary="E restock-ready proof only; no E live run without approval, no buying decision, and no O implementation.",
        )
    )

    if coverage_rows is None:
        coverage_status = "warn"
        coverage_value = "coverage_summary_missing"
        coverage_root = "The new E coverage summary has not been produced by a live E run yet."
        coverage_proof = "coverage_summary_missing"
    elif not coverage_rows:
        coverage_status = "warn"
        coverage_value = "coverage_summary_empty"
        coverage_root = "The E coverage summary exists but is empty."
        coverage_proof = "coverage_summary_empty"
    else:
        coverage_status = "ok"
        coverage_value = "coverage_summary_present"
        coverage_root = ""
        coverage_proof = ";".join(f"{key}={value}" for key, value in coverage_rows[-1].items())
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_coverage_summary_live",
            status=coverage_status,
            severity=_severity(coverage_status),
            value=coverage_value,
            producer="E005_build_study_report.py",
            expected_output="out/e_coverage_summary.csv",
            actual_proof=coverage_proof,
            source_path=str(coverage_path),
            summary="E should publish a one-row coverage summary that explains how much of the SKU universe has profit and truth proof.",
            root_cause_guess=coverage_root,
            manager_action="If still missing after the next approved E run, create an E coverage-output repair task.",
            safe_repair_boundary="E coverage output proof only; no E live run without approval.",
        )
    )

    if perf_rows is None:
        roi_status = "not_checked"
        roi_value = "waiting_for_performance_summary"
        roi_root = "ROI coverage waits until performance summary can be read."
    else:
        total = len(_sku_set(perf_rows))
        roi = len(
            {
                row.get("sku", "").strip()
                for row in perf_rows
                if row.get("sku", "").strip() and str(row.get("units_sold_source", "")).strip().lower() == "roi"
            }
        )
        velocity_only = len(
            {
                row.get("sku", "").strip()
                for row in perf_rows
                if row.get("sku", "").strip() and str(row.get("units_sold_source", "")).strip().lower() == "velocity"
            }
        )
        ratio = (roi / total) if total else 0.0
        roi_status = "warn" if total and ratio < 0.50 else "ok"
        roi_value = f"roi_skus={roi};total_skus={total};velocity_only_skus={velocity_only};roi_coverage_pct={ratio:.2%}"
        roi_root = "Many SKUs have velocity or stock information but no ROI-backed profit proof." if roi_status == "warn" else ""
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_roi_coverage",
            status=roi_status,
            severity=_severity(roi_status),
            value=roi_value,
            producer="E004_build_performance_summary.py",
            expected_output="ROI-backed rows should cover a believable share of the E SKU universe",
            actual_proof=roi_value,
            source_path=str(performance_path),
            summary="E should warn when most SKUs are velocity-only instead of ROI-backed business truth.",
            root_cause_guess=roi_root,
            manager_action="If warn, treat it as a confidence gap unless a required business decision depends on those rows.",
            safe_repair_boundary="E coverage proof only; no local DB alignment or downstream masking.",
        )
    )

    if study_rows is None:
        truth_status = "not_checked"
        truth_value = "waiting_for_study_report"
        truth_root = "Daily-truth coverage waits until the study report can be read."
    else:
        total_study = len(study_rows)
        blank_rows = [row for row in study_rows if _is_blankish(row.get("latest_daily_truth_state", ""))]
        explained_blank = 0
        for row in blank_rows:
            sales_truth_state = str(row.get("sales_truth_state", "") or "").strip().lower()
            missing_reason = str(row.get("missing_reason", "") or "").strip()
            if sales_truth_state and sales_truth_state not in {"nan", "none", "null", "not_available"}:
                explained_blank += 1
            elif missing_reason:
                explained_blank += 1
        blank_truth = len(blank_rows)
        unexplained_truth = blank_truth - explained_blank
        ratio = (unexplained_truth / total_study) if total_study else 0.0
        truth_status = "warn" if total_study and ratio > 0.25 else "ok"
        truth_value = (
            f"blank_truth_rows={blank_truth};explained_blank_truth_rows={explained_blank};"
            f"unexplained_truth_rows={unexplained_truth};study_rows={total_study};unexplained_pct={ratio:.2%}"
        )
        truth_root = "Many study rows have neither latest daily-truth state nor a sales-truth explanation." if truth_status == "warn" else ""
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_daily_truth_coverage",
            status=truth_status,
            severity=_severity(truth_status),
            value=truth_value,
            producer="E005_build_study_report.py",
            expected_output="study rows should explain daily truth state when available",
            actual_proof=truth_value,
            source_path=str(study_path),
            summary="E study output should explain rows with daily-truth state, sales-truth state, or a missing-proof reason.",
            root_cause_guess=truth_root,
            manager_action="If warn, create a proof-gap task only when daily-truth explanation is required for the next decision.",
            safe_repair_boundary="E study proof only; no downstream masking.",
        )
    )

    if perf_rows is None:
        guard_status = "not_checked"
        guard_value = "waiting_for_performance_summary"
        guard_root = "Restock readiness guard waits until performance summary can be read."
    elif {"restock_business_ready", "profit_confidence"}.issubset(perf_headers):
        bad_ready = [
            row.get("sku", "").strip()
            for row in perf_rows
            if str(row.get("restock_business_ready", "")).strip().lower() == "yes"
            and str(row.get("profit_confidence", "")).strip().lower() != "profit_clean"
        ]
        guard_status = "fail" if bad_ready else "ok"
        guard_value = f"restock_ready_without_clean_profit={len(bad_ready)}"
        guard_root = "At least one SKU is marked restock-business-ready without clean profit proof." if bad_ready else ""
    else:
        guard_status = "warn"
        guard_value = "restock_business_ready_not_live_yet"
        guard_root = "Latest E output does not yet separate stock pressure from business-ready reorder proof."
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_restock_profit_guard",
            status=guard_status,
            severity=_severity(guard_status),
            value=guard_value,
            producer="E004_build_performance_summary.py",
            expected_output="restock_business_ready=yes only when profit_confidence=profit_clean",
            actual_proof=guard_value,
            source_path=str(performance_path),
            summary="E should separate low-stock signals from profitable-enough reorder readiness.",
            root_cause_guess=guard_root,
            manager_action="If fail, create an E reconciliation or confidence-label repair task before trusting restock-ready rows.",
            safe_repair_boundary="E restock confidence proof only; no price, queue, Sheet, or O decision changes.",
        )
    )

    bridge_path = base / "out" / "systems" / "M" / "sellerboard_bridge" / SUMMARY_NAME
    bridge_rows = read_csv_rows(bridge_path)
    bridge_metrics = {row.get("metric", ""): row for row in bridge_rows}
    money_review_path = base / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv"
    money_review_summary_path = (
        base / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv"
    )
    money_review_rows = read_csv_rows(money_review_path)
    money_review_summary = {
        row.get("metric", ""): row for row in read_csv_rows(money_review_summary_path)
    }
    if money_review_rows:
        bridge_live_roi_safe = _money_review_metric(money_review_summary, "bridge_values_safe_for_live_roi")
        api_proved_rows = _summary_metric_int(money_review_summary, "api_proved_rows")
        bridge_estimate_rows = _summary_metric_int(money_review_summary, "sellerboard_bridge_estimate_rows")
        not_yet_proven_rows = _summary_metric_int(money_review_summary, "not_yet_proven_rows")
        b_source_handoff_ready = _money_review_metric(money_review_summary, "b_source_handoff_ready")
        b_source_chain_state = _money_review_metric(money_review_summary, "b_source_chain_state")
        b_source_bridge_estimate_rows = _summary_metric_int(
            money_review_summary, "b_source_sellerboard_bridge_estimate_rows"
        )
        b_source_not_yet_rows = _summary_metric_int(money_review_summary, "b_source_not_yet_proven_rows")
        if b_source_handoff_ready == "1":
            roi_money_state = "api_backed_safe"
        elif b_source_chain_state == "bridge_labelled_only" or b_source_bridge_estimate_rows > 0:
            roi_money_state = "bridge_labelled_only"
        elif b_source_chain_state == "not_yet_proven" or b_source_not_yet_rows > 0:
            roi_money_state = "not_yet_proven"
        elif bridge_live_roi_safe == "1":
            roi_money_state = "api_backed_safe"
        elif bridge_estimate_rows > 0:
            roi_money_state = "bridge_labelled_only"
        elif not_yet_proven_rows > 0:
            roi_money_state = "not_yet_proven"
        elif api_proved_rows > 0:
            roi_money_state = "api_backed_safe"
        else:
            roi_money_state = "not_reported"
        refund_state = _money_review_label(money_review_rows, "api_refund_money")
        sellerboard_return_gap_state = _money_review_label(money_review_rows, "sellerboard_return_refund_gap")
        commission_state = _money_review_label(money_review_rows, "commission_fee")
        fba_state = _money_review_label(money_review_rows, "fba_fee")
        shipping_income_state = _money_review_label(money_review_rows, "shipping_income")
        shipping_fee_state = _money_review_label(money_review_rows, "shipping_fee")
        b_money_source_path = f"{money_review_path};{money_review_summary_path}"
        b_money_source = "b067_refund_fee_shipping_gap_review"
    else:
        roi_money_state = _summary_metric(bridge_metrics, "roi_money_confidence_state") or "not_reported"
        bridge_live_roi_safe = _summary_metric(bridge_metrics, "bridge_values_safe_for_live_roi") or "0"
        refund_state = _summary_metric(bridge_metrics, "refund_api_proof_state") or "not_reported"
        sellerboard_return_gap_state = _summary_metric(
            bridge_metrics, "sellerboard_return_orders_missing_local_refund_posted_window"
        ) or "not_reported"
        commission_state = _summary_metric(bridge_metrics, "commission_api_proof_state") or "not_reported"
        fba_state = _summary_metric(bridge_metrics, "fba_fee_api_proof_state") or "not_reported"
        shipping_income_state = _summary_metric(bridge_metrics, "shipping_income_api_proof_state") or "not_reported"
        shipping_fee_state = _summary_metric(bridge_metrics, "shipping_fee_api_proof_state") or "not_reported"
        b_money_source_path = str(bridge_path)
        b_money_source = "sellerboard_bridge_summary"
    ready_skus = 0
    if perf_rows:
        ready_skus = len(
            {
                row.get("sku", "").strip()
                for row in perf_rows
                if row.get("sku", "").strip()
                and str(row.get("restock_business_ready", "")).strip().lower() == "yes"
            }
        )
    if perf_rows is None:
        money_status = "not_checked"
        money_value = "waiting_for_performance_summary"
        money_root = "E/B money dependency waits until E performance summary can be read."
    elif not bridge_rows and not money_review_rows:
        money_status = "not_checked"
        money_value = "waiting_for_b_money_summary"
        money_root = "E/B money dependency waits until the B money proof summary exists."
    elif roi_money_state == "api_backed_safe" and bridge_live_roi_safe == "1":
        money_status = "ok"
        money_value = (
            f"b_roi_money_confidence_state={roi_money_state};"
            f"bridge_values_safe_for_live_roi={bridge_live_roi_safe};"
            f"restock_business_ready_skus={ready_skus}"
        )
        money_root = ""
    else:
        money_status = "warn"
        money_value = (
            f"b_roi_money_confidence_state={roi_money_state};"
            f"bridge_values_safe_for_live_roi={bridge_live_roi_safe};"
            f"restock_business_ready_skus={ready_skus}"
        )
        money_root = "B money proof is not API-backed enough for E ROI/restocking to be treated as final business truth."
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_b_money_truth_dependency",
            status=money_status,
            severity=_severity(money_status),
            value=money_value,
            producer="sellerone_manager.hourly_mot",
            expected_output="B money-proof labels protect E ROI and restock outputs",
            actual_proof=(
                f"refund_api_proof_state={refund_state};"
                f"sellerboard_return_gap_state={sellerboard_return_gap_state};"
                f"commission_api_proof_state={commission_state};"
                f"fba_fee_api_proof_state={fba_state};"
                f"shipping_income_api_proof_state={shipping_income_state};"
                f"shipping_fee_api_proof_state={shipping_fee_state};"
                f"roi_money_confidence_state={roi_money_state};"
                f"bridge_values_safe_for_live_roi={bridge_live_roi_safe};"
                f"restock_business_ready_skus={ready_skus};"
                f"b_money_source={b_money_source}"
            ),
            source_path=f"{performance_path};{b_money_source_path}",
            summary="E ROI and restock outputs should stay warning-labelled when upstream B money proof is bridge-only or not yet proven.",
            root_cause_guess=money_root,
            manager_action=(
                "Keep E ROI/restocking as a confidence warning until B money proof is API-backed. "
                "Do not turn bridge-only money proof into automatic reorder decisions."
            ),
            safe_repair_boundary="E/B manager proof only; no E live run, B run, data correction, DB alignment, Sheet write, price change, queue edit, output deletion, or downstream masking.",
        )
    )
    refund_required = {
        "refund_unit_rate_30d",
        "refund_unit_rate_90d",
        "refund_units_30d",
        "sales_units_30d",
        "expected_refund_cost_per_unit_gbp",
        "refund_cost_basis",
        "refund_proof_state",
        "refund_sample_confidence",
    }
    if perf_rows is None:
        refund_status = "not_checked"
        refund_value = "waiting_for_performance_summary"
        refund_root = "E refund ROI proof waits until the E performance summary can be read."
        weak_ready: list[str] = []
        missing_refund_cols = sorted(refund_required)
    else:
        missing_refund_cols = sorted(refund_required - set(perf_headers))
        weak_states = {"", "not_yet_proven", "sellerboard_bridge_only", "bridge_labelled_only"}
        weak_ready = [
            row.get("sku", "").strip()
            for row in perf_rows
            if str(row.get("restock_business_ready", "")).strip().lower() == "yes"
            and str(row.get("refund_proof_state", "")).strip() in weak_states
        ]
        if missing_refund_cols:
            refund_status = "warn"
            refund_value = f"missing_refund_columns={len(missing_refund_cols)}"
            refund_root = "E performance summary does not yet carry refund-rate proof fields."
        elif weak_ready:
            refund_status = "warn"
            refund_value = f"restock_ready_with_weak_refund_proof={len(weak_ready)}"
            refund_root = "At least one restock-ready SKU still has weak refund proof."
        else:
            refund_status = "ok"
            refund_value = "refund_roi_fields_present"
            refund_root = ""
    rows.append(
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_refund_roi_proof_fields",
            status=refund_status,
            severity=_severity(refund_status),
            value=refund_value,
            producer="E004_build_performance_summary.py",
            expected_output="E performance summary carries refund-rate, refund-cost, proof-state, and confidence fields",
            actual_proof=(
                f"missing_columns={';'.join(missing_refund_cols)};"
                f"restock_ready_with_weak_refund_proof={len(weak_ready)}"
            ),
            source_path=str(performance_path),
            summary="E ROI should use API-backed refund drag where available and label weak refund proof before O consumes it.",
            root_cause_guess=refund_root,
            manager_action="Refresh or repair E refund proof fields before treating refund-adjusted ROI as business-ready.",
            safe_repair_boundary="E refund proof only; no live E run, B run, Sheet write, DB alignment, price change, queue edit, output deletion, or restock decision.",
        )
    )
    return rows


def _e_health_profile_rows(
    *,
    base: Path,
    observed_utc: str,
    now: datetime,
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    path = base / "out" / "cycle_alerts" / "checklist_E_split.csv"
    rows = read_csv_rows(path)
    rows_count = len(rows)
    age = file_age_hours(path, now)
    fail_count = sum(1 for row in rows if row.get("status", "").strip().lower() in {"fail", "failed", "blocked"})
    warn_count = sum(1 for row in rows if row.get("status", "").strip().lower() in {"warn", "warning", "stale_evidence"})
    step = _manifest_step(manifest, "A015_build_system_health_check.py:profile=e")
    notes = str(step.get("notes", "") or "")
    health_summary = manifest.get("health_summary", {}) if isinstance(manifest.get("health_summary", {}), dict) else {}
    current_cycle = bool(health_summary.get("current_cycle_evidence", False))
    status = status_from_age(age, warn_hours=E_DAILY_WARN_HOURS, fail_hours=E_DAILY_FAIL_HOURS)
    value = "current"
    root_cause = ""
    if not path.exists() or rows_count < 1:
        status = "fail"
        value = "missing_or_empty"
        root_cause = "E scoped health/profile checklist is missing or empty."
    elif not step:
        status = "fail"
        value = "manifest_step_missing"
        root_cause = "Latest E manifest does not show the E scoped health/profile step."
    elif str(step.get("rc", "0")) not in {"", "0"}:
        status = "fail"
        value = "health_step_failed"
        root_cause = "Latest E manifest recorded a nonzero E scoped health/profile return code."
    elif "split_fresh=1" not in notes or not current_cycle:
        status = "fail"
        value = "not_current_cycle_evidence"
        root_cause = "E scoped health/profile proof is not tied to the latest E run."
    elif fail_count:
        status = "fail"
        value = f"fail_count={fail_count}"
        root_cause = "E scoped health/profile contains active failures."
    elif warn_count and status != "fail":
        status = "warn"
        value = f"warn_count={warn_count}"
        root_cause = "E scoped health/profile contains warnings."
    elif status != "ok":
        value = "stale"
        root_cause = "E scoped health/profile proof is stale."
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_health_profile_current",
            status=status,
            severity=_severity(status),
            value=value,
            producer="A015_build_system_health_check.py:profile=e",
            expected_output="out/cycle_alerts/checklist_E_split.csv",
            actual_proof=(
                f"rows={rows_count};age_hours={_age_text(age)};fail_count={fail_count};warn_count={warn_count};"
                f"split_fresh={'1' if 'split_fresh=1' in notes else '0'};current_cycle_evidence={'1' if current_cycle else '0'}"
            ),
            age_hours=_age_text(age),
            row_count=str(rows_count),
            source_path=str(path),
            summary="E scoped health/profile proof should be current and tied to the latest E run.",
            root_cause_guess=root_cause,
            manager_action="If fail, package E scoped health proof repair. Do not use global health as a substitute.",
            safe_repair_boundary="E scoped health proof only; no global-health masking or E live run without approval.",
        )
    ]


def _e_lock_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    lock_paths = [
        base / "out" / "systems" / "E" / "live" / "E_cycle.lock",
        base / "out" / "E_cycle.lock",
    ]
    present: list[tuple[Path, dict[str, str], float | None, bool | None]] = []
    for path in lock_paths:
        fields = _read_lock_fields(path)
        if not fields:
            continue
        age_seconds = _lock_heartbeat_age_seconds(fields, now)
        if age_seconds is None:
            file_age = file_age_hours(path, now)
            age_seconds = None if file_age is None else file_age * 3600.0
        present.append((path, fields, age_seconds, _pid_alive(fields.get("pid", ""))))
    if not present:
        status = "ok"
        value = "clear"
        root_cause = ""
        age_text = ""
        actual = "no_lock_found"
    else:
        live_owner_keys: set[str] = set()
        stale_or_dead = False
        ages: list[float] = []
        for _path, fields, age_seconds, pid_alive in present:
            if isinstance(age_seconds, float):
                ages.append(age_seconds)
            owner_key = str(fields.get("pid", "") or fields.get("owner_label", "") or fields.get("owner", "")).strip()
            is_fresh = isinstance(age_seconds, float) and age_seconds < E_LOCK_FAIL_SECONDS and pid_alive is not False
            if is_fresh:
                live_owner_keys.add(owner_key or "unknown")
            else:
                stale_or_dead = True
        max_age = max(ages) if ages else None
        if len(live_owner_keys) > 1:
            status = "fail"
            value = "duplicate_owner"
            root_cause = "More than one E lock owner is visible."
        elif stale_or_dead or not live_owner_keys:
            status = "fail"
            value = "stale_or_dead_lock"
            root_cause = "E lock exists but heartbeat or process evidence is stale or dead."
        elif isinstance(max_age, float) and max_age >= E_LOCK_WARN_SECONDS:
            status = "warn"
            value = "lock_present_old"
            root_cause = "E lock is present longer than expected for the short E run."
        else:
            status = "ok"
            value = "single_owner"
            root_cause = ""
        age_text = "" if max_age is None else _age_text(max_age / 3600.0)
        actual = ";".join(
            f"{path.name}:pid={fields.get('pid', '')},age_seconds={_seconds_text(age)},pid_alive={pid_alive}"
            for path, fields, age, pid_alive in present
        )
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_lock_state",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_E_cycle.py",
            expected_output="no stale or duplicate E lock",
            actual_proof=actual,
            age_hours=age_text,
            source_path=";".join(str(path) for path in lock_paths),
            summary="E should not leave stale lock evidence after its analytics run.",
            root_cause_guess=root_cause,
            manager_action="If fail, package an E ownership-proof repair. Do not delete locks from MOT.",
            safe_repair_boundary="E ownership proof only; no lock deletion, worker restart, or E live run.",
        )
    ]


def _e_optional_publish_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    path = base / "out" / "e_publish_log.csv"
    rows_count = csv_row_count(path)
    age = file_age_hours(path, now)
    if rows_count is None:
        status = "not_checked"
        value = "not_verified"
        root_cause = "Optional E publish proof is missing, which is not an E runtime failure."
    elif rows_count < 1:
        status = "not_checked"
        value = "empty_optional_proof"
        root_cause = "Optional E publish proof exists but has no rows."
    elif status_from_age(age, warn_hours=E_DAILY_WARN_HOURS, fail_hours=E_DAILY_FAIL_HOURS) != "ok":
        status = "not_checked"
        value = "stale_optional_proof"
        root_cause = "Optional E publish proof is stale."
    else:
        status = "ok"
        value = "publish_proof_present"
        root_cause = ""
    return [
        mot_row(
            observed_utc=observed_utc,
            flow="E",
            check="e_optional_publish_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="E010_publish_e_outputs.py",
            expected_output="out/e_publish_log.csv",
            actual_proof=f"exists={1 if path.exists() else 0};rows={'' if rows_count is None else rows_count};age_hours={_age_text(age)}",
            age_hours=_age_text(age),
            row_count="" if rows_count is None else str(rows_count),
            source_path=str(path),
            summary="Optional E publishing proof stays not_verified unless real publish proof exists.",
            root_cause_guess=root_cause,
            manager_action="Do not create a repair from missing optional publish proof unless publishing becomes required.",
            safe_repair_boundary="Optional E publish proof only; no Sheet enablement or legacy Sheet write.",
        )
    ]


def _a_maintenance_handoff_rows(
    *,
    base: Path,
    observed_utc: str,
    manifest: dict[str, Any],
    manifest_path: Path | None,
) -> list[dict[str, str]]:
    proof_path = base / "out" / "systems" / "A" / "live" / "a_maintenance_handoff_latest.json"
    payload = _read_json(proof_path)
    latest_run_id = str(manifest.get("run_id", "") or "").strip()
    proof_run_id = str(payload.get("final_run_id", "") or "").strip()
    proof_status = str(payload.get("proof_status", "") or "").strip()
    cleanup = payload.get("cleanup_evidence", {})
    cleanup_clear = bool(cleanup.get("all_clear", False)) if isinstance(cleanup, dict) else False
    if not payload:
        status = "not_checked"
        value = "missing"
        root_cause = "A maintenance handoff proof has not been written yet."
    elif payload.get("_read_error") == "1":
        status = "fail"
        value = "read_error"
        root_cause = "A maintenance handoff proof exists but cannot be read."
    elif _a_interrupted_pending_normal_proof(manifest, payload):
        status = "not_checked"
        value = "interrupted_pending_next_normal_a_run"
        root_cause = "A proof run was interrupted after safe handoff evidence and cleanup; next normal A-owned run must prove completion."
    elif proof_status != "ok":
        status = "fail"
        value = proof_status or "not_ok"
        root_cause = "Latest A maintenance handoff proof recorded an unsafe or failed handoff."
    elif latest_run_id and proof_run_id != latest_run_id:
        status = "not_checked"
        value = "stale_for_latest_manifest"
        root_cause = "A maintenance handoff proof is older than the latest A manifest."
    elif not cleanup_clear:
        status = "fail"
        value = "cleanup_not_clear"
        root_cause = "A maintenance handoff proof says maintenance markers were not fully cleared."
    else:
        status = "ok"
        value = "matched_latest_run"
        root_cause = ""
    rows = [
        mot_row(
            observed_utc=observed_utc,
            check="a_maintenance_handoff_proof",
            status=status,
            severity=_severity(status),
            value=value,
            producer="scripts/cycles/run_A_all.py",
            expected_output="out/systems/A/live/a_maintenance_handoff_latest.json",
            actual_proof=f"latest_run_id={latest_run_id};proof_run_id={proof_run_id};proof_status={proof_status}",
            source_path=str(proof_path if proof_path.exists() else (manifest_path or proof_path)),
            summary="A should leave durable proof that it requested maintenance, waited safely, became active, and cleared markers.",
            root_cause_guess=root_cause,
            manager_action=(
                "Park this handoff proof until the next normal A-owned run; do not run A or A015 from MOT."
                if status == "not_checked" and value == "interrupted_pending_next_normal_a_run"
                else "If fail, treat A/B handoff safety as blocked. If not_checked, keep it as a proof-mapping gap "
                "until the next full A-owned run writes this artifact."
            ),
            safe_repair_boundary="A runner proof-writing only; do not create, delete, or edit lock files from MOT.",
        )
    ]
    return rows


def _a_interrupted_pending_normal_proof(manifest: dict[str, Any], payload: dict[str, Any]) -> bool:
    if not manifest or not payload or payload.get("_read_error") == "1":
        return False
    latest_run_id = str(manifest.get("run_id", "") or "").strip()
    proof_run_id = str(payload.get("final_run_id", "") or "").strip()
    if latest_run_id and proof_run_id and latest_run_id != proof_run_id:
        return False
    manifest_state = str(manifest.get("final_state", "") or "").strip().lower()
    payload_state = str(payload.get("final_state", "") or "").strip().lower()
    final_exit_code = str(payload.get("final_exit_code", "") or "").strip()
    cleanup = payload.get("cleanup_evidence", {})
    cleanup_clear = bool(cleanup.get("all_clear", False)) if isinstance(cleanup, dict) else False
    b_ready = payload.get("b_ready_evidence", {})
    a_active = payload.get("a_active_evidence", {})
    b_ready_seen = bool(b_ready.get("exists", False)) if isinstance(b_ready, dict) else False
    a_active_seen = bool(a_active.get("exists", False)) if isinstance(a_active, dict) else False
    interrupted_step = False
    for step in manifest.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_text = " ".join(
            str(step.get(key, "") or "")
            for key in ("rc", "notes", "step_status", "verification_status")
        ).lower()
        if "interrupted" in step_text or str(step.get("rc", "")).strip() in {"130", "-1073741510"}:
            interrupted_step = True
            break
    return (
        manifest_state in {"partial", "interrupted"}
        and payload_state in {"partial", "interrupted", "failed", ""}
        and cleanup_clear
        and b_ready_seen
        and a_active_seen
        and (final_exit_code == "130" or interrupted_step)
    )


def _a_lock_rows(*, base: Path, observed_utc: str, now: datetime) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lock_paths = [
        base / "out" / "systems" / "A" / "live" / "run_cycle.lock",
        base / "out" / "run_cycle.lock",
    ]
    found = [path for path in lock_paths if path.exists()]
    if not found:
        return [
            mot_row(
                observed_utc=observed_utc,
                check="a_cycle_lock",
                status="ok",
                severity="info",
                value="not_running",
                producer="scripts/cycles/run_A_all.py",
                expected_output="A lock absent unless A is active",
                actual_proof="no_lock_found",
                source_path=";".join(str(path) for path in lock_paths),
                summary="No A lock is present, so A is not currently claiming to run.",
                manager_action="No manager action unless A proof files are stale.",
                safe_repair_boundary="A ownership proof only; do not start A from MOT.",
            )
        ]
    for path in found:
        age = file_age_hours(path, now)
        status = "fail" if age is not None and age >= A_LOCK_FAIL_HOURS else "warn"
        rows.append(
            mot_row(
                observed_utc=observed_utc,
                check="a_cycle_lock",
                status=status,
                severity=_severity(status),
                value="lock_present",
                producer="scripts/cycles/run_A_all.py",
                expected_output="fresh A lock only while A is active",
                actual_proof=f"lock_age_hours={_age_text(age)}",
                age_hours=_age_text(age),
                source_path=str(path),
                summary="A lock is present. This is only healthy briefly while A is actively running.",
                root_cause_guess="A lock may be stale." if status == "fail" else "A appears to be running now.",
                manager_action="If old, create a Codex task to inspect stale A ownership before starting or trusting A.",
                safe_repair_boundary="A ownership proof only; do not delete locks unless a stale-owner repair task is approved.",
            )
        )
    return rows


def _annotate_changes(rows: list[dict[str, str]], previous_rows: list[dict[str, str]]) -> None:
    previous = {(row.get("flow", ""), row.get("check", "")): row for row in previous_rows}
    for row in rows:
        prev = previous.get((row.get("flow", ""), row.get("check", "")), {})
        row["previous_status"] = prev.get("status", "")
        changed = (
            not prev
            or prev.get("status", "") != row.get("status", "")
            or prev.get("value", "") != row.get("value", "")
        )
        row["changed_since_previous"] = "1" if changed else "0"


def build_mot_worklist(
    result: dict[str, Any],
    *,
    previous_worklist: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    observed = str(result.get("observed_utc", ""))
    result_flow = str(result.get("flow", "A")).upper()
    quiet = bool(result.get("quiet_autonomy_active"))
    previous = {row.get("work_item_id", ""): row for row in previous_worklist or [] if row.get("work_item_id")}
    observed_flows = {
        str(row.get("flow", result_flow)).strip().upper()
        for row in result.get("rows", [])
        if str(row.get("flow", result_flow)).strip()
    }
    active_items = {
        _work_item_id(str(row.get("flow", result_flow)).upper(), row.get("check", ""))
        for row in result.get("rows", [])
        if _row_needs_work(row, quiet_autonomy=quiet)
    }
    controlled_items = _controlled_warning_work_items(result.get("rows", []))
    parked_items = {
        _work_item_id(str(row.get("flow", result_flow)).upper(), row.get("check", "")): row
        for row in result.get("rows", [])
        if (
            _row_parks_previous_work(row)
            or _row_parks_for_quiet_autonomy(row, quiet_autonomy=quiet)
            or _row_is_summary_only(row)
        )
    }
    work_rows: list[dict[str, str]] = []

    for row in result.get("rows", []):
        if not _row_needs_work(row, quiet_autonomy=quiet):
            continue
        item_id = _work_item_id(row.get("flow", "A"), row.get("check", ""))
        prev = previous.get(item_id, {})
        prev_status = prev.get("status", "")
        if item_id in controlled_items:
            work_item = _work_item_from_mot_row(row, observed=observed, previous=prev, status="parked")
            work_item["luke_action_required"] = "0"
            work_item["notes"] = controlled_items[item_id]
            work_rows.append(work_item)
            continue
        if row.get("luke_action_required") == "1" or row.get("status") == "decision_needed":
            status = "blocked_needs_luke"
        elif prev_status == "blocked_needs_luke":
            status = "new"
        elif prev_status == "fixed_needs_retest":
            status = "retest_failed"
        elif prev_status in MOT_ACTIVE_WORK_STATUSES:
            status = prev_status
        else:
            status = "new"
        work_rows.append(_work_item_from_mot_row(row, observed=observed, previous=prev, status=status))

    for item_id, prev in previous.items():
        if not item_id or item_id in active_items:
            continue
        prev_flow = _work_item_flow(prev, item_id=item_id, default_flow=result_flow)
        if result_flow == "ALL":
            if prev_flow not in observed_flows:
                work_rows.append(prev)
                continue
        elif prev_flow != result_flow:
            work_rows.append(prev)
            continue
        if item_id in parked_items and prev.get("status") in MOT_ACTIVE_WORK_STATUSES | MOT_TERMINAL_WORK_STATUSES:
            parked = dict(prev)
            parked["observed_utc"] = observed
            parked["updated_utc"] = observed
            parked["last_seen_utc"] = observed
            parked["status"] = "parked"
            parked["luke_action_required"] = parked_items[item_id].get("luke_action_required", "0") or "0"
            parked["notes"] = parked_items[item_id].get("manager_action") or "Latest MOT parked this item."
            work_rows.append(parked)
            continue
        if prev.get("status") in MOT_ACTIVE_WORK_STATUSES:
            proved = dict(prev)
            proved["observed_utc"] = observed
            proved["updated_utc"] = observed
            proved["last_seen_utc"] = observed
            proved["status"] = "proved"
            proved["luke_action_required"] = "0"
            proved["notes"] = "Latest MOT no longer sees this failure."
            work_rows.append(proved)
        elif prev.get("status") in MOT_TERMINAL_WORK_STATUSES:
            terminal = dict(prev)
            terminal["luke_action_required"] = "0"
            work_rows.append(terminal)

    _assign_mot_job_refs(work_rows)
    return sorted(work_rows, key=lambda row: (_work_priority_rank(row.get("priority", "")), row.get("work_item_id", "")))


def _controlled_warning_work_items(rows: list[dict[str, str]]) -> dict[str, str]:
    by_key = {
        (str(row.get("flow", "")).upper(), str(row.get("check", ""))): row
        for row in rows
    }
    controlled: dict[str, str] = {}
    b_readiness = by_key.get(("B", "b_management_ready_for_maintenance"), {})
    if b_readiness.get("status") == "warn":
        value = str(b_readiness.get("value", "") or "").strip()
        note = "B is manager-watchable, but the warning remains until the underlying B proof lanes clear."
        if value:
            note = f"{value}. {note}"
        controlled[_work_item_id("B", "b_management_ready_for_maintenance")] = note
    marketplace_coverage = by_key.get(("B", "b_marketplace_coverage_report"), {})
    if marketplace_coverage.get("status") == "warn":
        value = str(marketplace_coverage.get("value", "") or "").strip()
        proof = str(marketplace_coverage.get("actual_proof", "") or "")
        if "fail_rows=0" in proof and "status_diff_warn_rows=" in proof:
            note = (
                "Marketplace coverage is warning-labelled, not failed. "
                "Current warnings are comparison/status rows and there is no missing shipped-order or shared-cursor failure."
            )
            if value:
                note = f"{value}. {note}"
            controlled[_work_item_id("B", "b_marketplace_coverage_report")] = note
    pnl_daily = by_key.get(("B", "b_pnl_daily"), {})
    if pnl_daily.get("status") == "warn":
        value = str(pnl_daily.get("value", "") or "").strip()
        proof = str(pnl_daily.get("actual_proof", "") or "")
        note = (
            "P and L exists but is stale against the manager warning window. "
            "This is parked as waiting producer refresh proof; MOT must not run D001, run B, or rewrite finance data."
        )
        if proof:
            note = f"{note} Proof: {proof}."
        if value:
            note = f"{value}. {note}"
        controlled[_work_item_id("B", "b_pnl_daily")] = note
    h_reliability = by_key.get(("H", "h_reliability_window"), {})
    if h_reliability.get("status") == "fail":
        value = str(h_reliability.get("value", "") or "").strip()
        proof = str(h_reliability.get("actual_proof", "") or "")
        failed_segments = [segment for segment in proof.split("|") if ":failed:" in segment]
        if failed_segments == ["H_20260604T101005Z:failed:failed"]:
            note = (
                "Known failed H run H_20260604T101005Z remains inside the last-10 reliability window. "
                "This is parked until newer normal H receipts age it out; if a different H run fails, "
                "create a fresh bounded H failed-run proof packet. Do not run H, publish, change prices, "
                "edit queues, write Sheets, align DB facts, delete outputs, or restart workers from MOT."
            )
            if value:
                note = f"{value}. {note}"
            controlled[_work_item_id("H", "h_reliability_window")] = note
    h_floor_source = by_key.get(("H", "h_token_floor_source_guard"), {})
    if h_floor_source.get("status") == "warn":
        value = str(h_floor_source.get("value", "") or "").strip()
        if "unknown_source_rows=0" in value:
            note = (
                "H now labels token-floor cost trust from B proof instead of treating fallback token cost as clean. "
                "This is parked as manager-visible truth: affected floors stay blocked from clean proof until B batch-link proof "
                "or a protected historical correction clears them. Do not run H, publish, change prices, edit queues, "
                "write Sheets, align DB facts, delete outputs, or restart workers from this warning."
            )
            if value:
                note = f"{value}. {note}"
            controlled[_work_item_id("H", "h_token_floor_source_guard")] = note
    money_gap = by_key.get(("B", "b_refund_fee_shipping_gap_review"), {})
    if money_gap.get("status") == "warn":
        value = str(money_gap.get("value", "") or "").strip()
        note = (
            "B067 labels refund, fee, shipping, ROI, and restock money proof. "
            "The warning is parked because Sellerboard bridge gaps and downstream E/O confidence rows remain blocked from live ROI/restocking until a future API proof packet clears them."
        )
        if value:
            note = f"{value}. {note}"
        controlled[_work_item_id("B", "b_refund_fee_shipping_gap_review")] = note
    level3_fee_map = by_key.get(("B", "b_level3_fee_shipping_api_proof_map"), {})
    if level3_fee_map.get("status") == "warn":
        value = str(level3_fee_map.get("value", "") or "").strip()
        note = (
            "B068 maps fee and shipping fields to the existing Level 3 API-backed money files. "
            "The warning is parked because any source-missing or raw-only fields stay blocked from live ROI/restocking until a follow-up proof packet clears the official-output path."
        )
        if value:
            note = f"{value}. {note}"
        controlled[_work_item_id("B", "b_level3_fee_shipping_api_proof_map")] = note
    fallback_reconcile = by_key.get(("B", "b_fallback_cost_proof_reconciliation"), {})
    if fallback_reconcile.get("status") == "warn":
        value = str(fallback_reconcile.get("value", "") or "").strip()
        note = (
            "B071 has reconciled the mismatch: source-token proof is traceable, but affected fallback costs are not clean H/O trust "
            "where the Sheet comparison says batch-link proof is still needed. This stays parked unless a protected historical correction is proposed."
        )
        if value:
            note = f"{value}. {note}"
        controlled[_work_item_id("B", "b_fallback_cost_proof_reconciliation")] = note
    refund_workpack = by_key.get(("B", "b_refund_return_warning_workpack"), {})
    if refund_workpack.get("status") == "ok":
        workpack_note = "B051 workpack classifies the current refund-return bridge warnings into bounded lanes"
        workpack_value = str(refund_workpack.get("value", "") or "").strip()
        if workpack_value:
            workpack_note = f"{workpack_note} ({workpack_value})"
        note = (
            f"{workpack_note}; "
            "the bridge remains warning-labelled, but this generic work item is parked until a lane-specific packet runs."
        )
        coverage_audit = by_key.get(("B", "b_amazon_return_coverage_audit"), {})
        if coverage_audit.get("status") == "ok":
            note = (
                f"{workpack_note}. "
                f"B052 coverage audit says {coverage_audit.get('value', '')}. "
                "The bridge remains warning-labelled and stock recovery stays blocked from ROI/restocking until lane-specific proof or an approved exception clears it."
            )
        allocation_audit = by_key.get(("B", "b_original_allocation_gap_audit"), {})
        if coverage_audit.get("status") == "ok" and allocation_audit.get("status") == "ok":
            note = (
                f"{workpack_note}. "
                f"B052 coverage audit says {coverage_audit.get('value', '')}. "
                f"B053 allocation audit says {allocation_audit.get('value', '')}. "
                "The bridge remains warning-labelled and stock recovery stays blocked from ROI/restocking until lane-specific proof or an approved exception clears it."
            )
        recovery_proof = by_key.get(("B", "b_original_order_recovery_proof"), {})
        if coverage_audit.get("status") == "ok" and allocation_audit.get("status") == "ok" and recovery_proof.get("status") == "ok":
            note = (
                f"{workpack_note}. "
                f"B052 coverage audit says {coverage_audit.get('value', '')}. "
                f"B053 allocation audit says {allocation_audit.get('value', '')}. "
                f"B054 original-order recovery proof says {recovery_proof.get('value', '')}. "
                "The bridge remains warning-labelled and stock recovery stays blocked from ROI/restocking until API order recovery, protected promotion, or an approved exception clears the lane."
            )
        recovery_fetch = by_key.get(("B", "b_original_order_recovery_fetch"), {})
        if (
            coverage_audit.get("status") == "ok"
            and allocation_audit.get("status") == "ok"
            and recovery_proof.get("status") == "ok"
            and recovery_fetch.get("status") == "ok"
        ):
            note = (
                f"{workpack_note}. "
                f"B052 coverage audit says {coverage_audit.get('value', '')}. "
                f"B053 allocation audit says {allocation_audit.get('value', '')}. "
                f"B054 original-order recovery proof says {recovery_proof.get('value', '')}. "
                f"B055 fetch preview/result says {recovery_fetch.get('value', '')}. "
                "The bridge remains warning-labelled and stock recovery stays blocked from ROI/restocking until API order recovery, protected promotion, or an approved exception clears the lane."
            )
        allocation_preview = by_key.get(("B", "b_original_sale_allocation_repair_preview"), {})
        if (
            coverage_audit.get("status") == "ok"
            and allocation_audit.get("status") == "ok"
            and recovery_proof.get("status") == "ok"
            and recovery_fetch.get("status") == "ok"
            and allocation_preview.get("status") == "ok"
        ):
            note = (
                f"{workpack_note}. "
                f"B052 coverage audit says {coverage_audit.get('value', '')}. "
                f"B053 allocation audit says {allocation_audit.get('value', '')}. "
                f"B054 original-order recovery proof says {recovery_proof.get('value', '')}. "
                f"B055 fetch preview/result says {recovery_fetch.get('value', '')}. "
                f"B056 allocation preview says {allocation_preview.get('value', '')}. "
                "The bridge remains warning-labelled and stock recovery stays blocked from ROI/restocking until protected allocation repair or an approved exception clears the lane."
            )
        allocation_apply = by_key.get(("B", "b_original_sale_allocation_repair_apply"), {})
        if (
            coverage_audit.get("status") == "ok"
            and allocation_audit.get("status") == "ok"
            and recovery_proof.get("status") == "ok"
            and recovery_fetch.get("status") == "ok"
            and allocation_preview.get("status") == "ok"
            and allocation_apply.get("status") == "ok"
        ):
            note = (
                f"{workpack_note}. "
                f"B052 coverage audit says {coverage_audit.get('value', '')}. "
                f"B053 allocation audit says {allocation_audit.get('value', '')}. "
                f"B054 original-order recovery proof says {recovery_proof.get('value', '')}. "
                f"B055 fetch preview/result says {recovery_fetch.get('value', '')}. "
                f"B056 allocation preview says {allocation_preview.get('value', '')}. "
                f"B057 allocation apply says {allocation_apply.get('value', '')}. "
                "The original sale-allocation lane is applied. Remaining refund-return bridge warnings stay parked by their own lanes; Sellerboard and weak stock-recovery values remain blocked from ROI/restocking."
            )
        disposition_swap = by_key.get(("B", "b_disposition_correction_swap_apply"), {})
        disposition_apply = by_key.get(("B", "b_disposition_correction_apply_preview"), {})
        original_conflict = by_key.get(("B", "b_original_return_status_conflict_preview"), {})
        original_apply_preview = by_key.get(("B", "b_original_return_status_apply_preview"), {})
        if (
            disposition_swap.get("status") == "ok"
            and disposition_apply.get("status") == "ok"
            and original_conflict.get("status") == "ok"
        ):
            note = (
                f"{workpack_note}. "
                f"B062 swap apply says {disposition_swap.get('value', '')}. "
                f"B061 disposition apply preview says {disposition_apply.get('value', '')}. "
                f"B045 original-token preview says {original_conflict.get('value', '')}. "
                "Remaining refund-return bridge warnings stay parked by their named lanes; Sellerboard and weak stock-recovery values remain blocked from ROI/restocking."
            )
        if (
            disposition_swap.get("status") == "ok"
            and disposition_apply.get("status") == "ok"
            and original_conflict.get("status") == "ok"
            and original_apply_preview.get("status") == "ok"
        ):
            note = (
                f"{workpack_note}. "
                f"B062 swap apply says {disposition_swap.get('value', '')}. "
                f"B061 disposition apply preview says {disposition_apply.get('value', '')}. "
                f"B045 original-token preview says {original_conflict.get('value', '')}. "
                f"B063 original-token apply preview says {original_apply_preview.get('value', '')}. "
                "Remaining refund-return bridge warnings stay parked by their named lanes; Sellerboard and weak stock-recovery values remain blocked from ROI/restocking."
            )
        controlled[_work_item_id("B", "b_refund_return_token_bridge")] = note
    return controlled


def _work_item_flow(row: dict[str, str], *, item_id: str, default_flow: str) -> str:
    flow = row.get("flow", "").strip().upper()
    if flow:
        return flow
    parts = item_id.split("_", 2)
    if len(parts) >= 2 and parts[0] == "MOT" and parts[1]:
        return parts[1].upper()
    return default_flow


def _row_needs_work(row: dict[str, str], *, quiet_autonomy: bool = False) -> bool:
    if _row_is_summary_only(row):
        return False
    if _row_parks_for_quiet_autonomy(row, quiet_autonomy=quiet_autonomy):
        return False
    if row.get("status") in {"fail", "decision_needed"} or row.get("luke_action_required") == "1":
        return True
    return row.get("status") == "warn" and row.get("check") in MOT_WARN_WORK_CHECKS


def _row_is_summary_only(row: dict[str, str]) -> bool:
    return (row.get("flow", "").upper(), row.get("check", "")) in MOT_SUMMARY_ONLY_CHECKS


def _row_parks_previous_work(row: dict[str, str]) -> bool:
    if row.get("status") != "not_checked":
        return False
    text = " ".join(
        [
            row.get("value", ""),
            row.get("manager_action", ""),
            row.get("root_cause_guess", ""),
        ]
    ).lower()
    return "park" in text


def _row_parks_for_quiet_autonomy(row: dict[str, str], *, quiet_autonomy: bool = False) -> bool:
    if not quiet_autonomy:
        return False
    if row.get("status") != "warn":
        return False
    return row.get("flow", "").upper() == "B" and row.get("check") in {
        "b_order_truth_completion",
        "b_sellerboard_refund_fee_roi_bridge",
    }


def _work_priority_rank(priority: str) -> int:
    return {"high": 0, "normal": 1, "low": 2}.get(priority, 9)


def _mot_job_ref(flow: str, check: str, title: str = "") -> str:
    flow = str(flow or "M").strip().upper()
    if flow == "B" and str(check or "").strip() == "b_fallback_cost_proof_reconciliation":
        return "B-FALLBACK-PROOF-RECONCILE"
    if flow == "B" and str(check or "").strip() == "b_fallback_token_cost_audit":
        return "B-FALLBACK-COST-AUDIT"
    if flow == "H" and str(check or "").strip() == "h_token_floor_source_guard":
        return "H-TOKEN-FLOOR-SOURCE-GUARD"
    if flow == "F" and str(check or "").strip() == "f_live_owner_status":
        return "F-SCANNER-PROGRESS"
    words = re.findall(r"[A-Za-z0-9]+", f"{title} {check}".upper().replace("RETURNEDTOKEN", "RETURNED TOKEN"))
    stop = {
        "MOT",
        "NEEDS",
        "REPAIR",
        "LUKE",
        "DECISION",
        "PROTECTED",
        "STATUS",
        "STATE",
        "APPLY",
        "LIVE",
        "RETURN",
        "RETURNED",
        "PROOF",
        "PRICE",
        "LIST",
        "LATEST",
        flow,
    }
    tokens: list[str] = []
    for word in words:
        if word in stop or (len(word) == 1 and word.isalpha()):
            continue
        if word not in tokens:
            tokens.append(word)
    if "EMAIL" in tokens and "SOURCE" in tokens:
        tokens = ["EMAIL", "SOURCE"]
    elif "ORIGINAL" in tokens and "TOKEN" in tokens:
        tokens = ["ORIGINAL", "TOKEN"]
    else:
        tokens = tokens[:3]
    return "-".join([flow] + (tokens or ["JOB"]))


def _assign_mot_job_refs(rows: list[dict[str, str]]) -> None:
    used: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: item.get("work_item_id", "")):
        desired = str(row.get("job_ref") or "").strip() or _mot_job_ref(
            row.get("flow", ""),
            row.get("check", ""),
            row.get("title", ""),
        )
        desired = re.sub(r"[^A-Za-z0-9]+", "-", desired.upper()).strip("-") or "M-JOB"
        count = used.get(desired, 0) + 1
        used[desired] = count
        row["job_ref"] = desired if count == 1 else f"{desired}-{count:02d}"


def _work_item_from_mot_row(
    row: dict[str, str],
    *,
    observed: str,
    previous: dict[str, str],
    status: str,
) -> dict[str, str]:
    seen_count = 1
    try:
        seen_count = int(float(previous.get("seen_count", "0") or "0")) + 1
    except ValueError:
        seen_count = 1
    check = row.get("check", "")
    flow = row.get("flow", "A").upper()
    title = f"{flow} MOT: {check} needs repair"
    if row.get("luke_action_required") == "1":
        title = f"{flow} MOT: {check} needs Luke decision"
    job_ref = previous.get("job_ref") or row.get("job_ref") or _mot_job_ref(flow, check, title)
    if flow == "H" and check == "h_token_floor_source_guard":
        job_ref = "H-TOKEN-FLOOR-SOURCE-GUARD"
    if flow == "F" and check == "f_live_owner_status":
        job_ref = "F-SCANNER-PROGRESS"
    return {
        "observed_utc": observed,
        "created_utc": previous.get("created_utc") or observed,
        "updated_utc": observed,
        "last_seen_utc": observed,
        "seen_count": str(seen_count),
        "work_item_id": _work_item_id(flow, check),
        "job_ref": job_ref,
        "flow": flow,
        "check": check,
        "producer": row.get("producer", ""),
        "title": title,
        "status": status,
        "priority": "high" if row.get("status") in {"fail", "decision_needed"} else "normal",
        "source_path": row.get("source_path", ""),
        "root_cause_guess": row.get("root_cause_guess", ""),
        "manager_action": row.get("manager_action", ""),
        "allowed_scope": row.get("safe_repair_boundary", ""),
        "forbidden_actions": MOT_FORBIDDEN_ACTIONS.get(flow, A_FORBIDDEN_ACTIONS),
        "proof_required": f"Retest with `{row.get('retest_command', _retest_command(flow))}` and confirm `{check}` is ok.",
        "retest_command": row.get("retest_command", _retest_command(flow)),
        "safe_repair_boundary": row.get("safe_repair_boundary", ""),
        "luke_action_required": row.get("luke_action_required", "0"),
        "notes": row.get("value", ""),
    }


def build_retest_queue(worklist_rows: list[dict[str, str]], observed_utc: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in worklist_rows:
        if row.get("status") not in {"fixed_needs_retest", "retest_failed"}:
            continue
        rows.append(
            {
                "observed_utc": observed_utc,
                "work_item_id": row.get("work_item_id", ""),
                "flow": row.get("flow", ""),
                "check": row.get("check", ""),
                "status": "pending" if row.get("status") == "fixed_needs_retest" else "failed",
                "retest_command": row.get("retest_command", ""),
                "expected_result": f"{row.get('check', '')}=ok",
                "source_path": row.get("source_path", ""),
                "notes": "Worker repair must be proven by MOT retest before the manager can mark it proved.",
            }
        )
    return rows


def update_mot_work_item_status(
    *,
    output_dir: Path,
    work_item_id: str,
    status: str,
    note: str = "",
    observed_utc: str | None = None,
) -> dict[str, str]:
    mot_dir = output_dir / "mot"
    path = mot_dir / "mot_worklist.csv"
    rows = read_csv_rows(path)
    allowed = MOT_ACTIVE_WORK_STATUSES | MOT_TERMINAL_WORK_STATUSES
    if status not in allowed:
        raise ValueError(f"unsupported MOT worklist status: {status}")
    observed = observed_utc or utc_now_text()
    changed: dict[str, str] | None = None
    for row in rows:
        if row.get("work_item_id") != work_item_id:
            continue
        row["status"] = status
        row["updated_utc"] = observed
        row["luke_action_required"] = "1" if status == "blocked_needs_luke" else "0"
        if note:
            row["notes"] = note
        changed = row
        break
    if changed is None:
        raise ValueError(f"MOT work item not found: {work_item_id}")
    write_csv(path, MOT_WORKLIST_COLUMNS, rows)
    retest_rows = build_retest_queue(rows, observed)
    write_csv(mot_dir / "mot_retest_queue.csv", MOT_RETEST_QUEUE_COLUMNS, retest_rows)
    return changed


def build_hourly_mot_markdown(result: dict[str, Any], worklist_rows: list[dict[str, str]] | None = None) -> str:
    rows = result["rows"]
    worklist_rows = worklist_rows or []
    flow = str(result.get("flow", "A")).upper()
    is_rollup = flow == "ALL"
    flow_label = str(result.get("flows", "")).replace(",", "/") if is_rollup else flow
    if not flow_label:
        flow_label = "/".join(SUPPORTED_MOT_FLOWS) if is_rollup else flow
    fail_rows = [row for row in rows if row["status"] == "fail"]
    warn_rows = [row for row in rows if row["status"] == "warn"]
    decision_rows = [row for row in rows if row["status"] == "decision_needed" or row.get("luke_action_required") == "1"]
    lines = [
        "# SellerOne Independent MOT",
        "",
        f"Observed UTC: {result['observed_utc']}",
        f"Flow: {flow_label}",
        f"Status: {result['status']}",
        f"Fails: {result['fail_count']}",
        f"Warnings: {result['warn_count']}",
        f"Decisions: {result.get('decision_count', 0)}",
        "",
        "## Plain English",
    ]
    if decision_rows:
        lines.append("The MOT found at least one item that needs Luke before repair can continue.")
    elif fail_rows:
        if is_rollup:
            lines.append("At least one cycle is not proven safe from independent evidence. The manager worklist keeps the failing cycle visible until its own MOT clears.")
        else:
            lines.append(f"{flow} is not proven safe from independent evidence. Treat downstream data as suspect until the failed rows are understood.")
    elif warn_rows:
        lines.append(f"{flow_label} has usable proof, but some evidence is old or incomplete.")
    else:
        if is_rollup:
            lines.append(f"{flow_label} have current independent proof from their flow-specific MOT files.")
        elif flow == "B":
            lines.append("B has fresh independent proof from outside checks. The old checklist is only a clue, not the sign-off.")
        else:
            lines.append(f"{flow} has fresh independent proof from files and database checks.")
    lines.extend(["", "## Failed Checks"])
    if fail_rows:
        for row in fail_rows:
            changed = "new/change" if row.get("changed_since_previous") == "1" else "unchanged"
            prefix = f"{row.get('flow', '')} / " if is_rollup else ""
            lines.append(f"- {prefix}{row['check']}: {row['value']} ({changed}) - {row['manager_action']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Warning Checks"])
    if warn_rows:
        for row in warn_rows:
            changed = "new/change" if row.get("changed_since_previous") == "1" else "unchanged"
            prefix = f"{row.get('flow', '')} / " if is_rollup else ""
            lines.append(f"- {prefix}{row['check']}: {row['value']} ({changed}) - {row['manager_action']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Worklist"])
    active = [row for row in worklist_rows if row.get("status") in MOT_ACTIVE_WORK_STATUSES]
    if active:
        for row in active[:10]:
            lines.append(f"- {row.get('job_ref') or row.get('work_item_id')}: {row.get('status')} - {row.get('title')}")
    else:
        lines.append("- No active MOT work item.")
    lines.extend(
        [
            "",
            "## Safety",
            f"- This MOT did not run {flow_label}.",
            "- This MOT did not call Amazon.",
            "- This MOT did not use AI tokens.",
            "- This MOT did not write Sheets, change prices, edit queues, or repair worker scripts.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_mot_rollup_result(
    rows: list[dict[str, str]],
    *,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or _latest_row_observed_utc(rows) or utc_now_text()
    ordered_rows = sorted(
        rows,
        key=lambda row: (
            SUPPORTED_MOT_FLOWS.index(row.get("flow", "Z")) if row.get("flow", "Z") in SUPPORTED_MOT_FLOWS else 99,
            row.get("check", ""),
        ),
    )
    result = _result_from_rows(observed, "ALL", ordered_rows)
    result["flows"] = ",".join(flow for flow in SUPPORTED_MOT_FLOWS if any(row.get("flow") == flow for row in ordered_rows))
    result["flow_count"] = len({row.get("flow", "") for row in ordered_rows if row.get("flow", "")})
    return result


def _latest_row_observed_utc(rows: list[dict[str, str]]) -> str:
    values = sorted(str(row.get("observed_utc", "")).strip() for row in rows if str(row.get("observed_utc", "")).strip())
    return values[-1] if values else ""


def _flow_mot_paths(output_dir: Path, flow: str) -> dict[str, Path]:
    flow_name = flow.upper()
    flow_key = flow_name.lower()
    return {
        f"hourly_mot_{flow_key}_csv": output_dir / f"hourly_mot_{flow_name}.csv",
        f"hourly_mot_{flow_key}_json": output_dir / f"hourly_mot_{flow_name}.json",
    }


def _write_single_flow_mot_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    flow = str(result.get("flow", "A")).upper()
    paths = _flow_mot_paths(output_dir, flow)
    previous_rows = read_csv_rows(paths[f"hourly_mot_{flow.lower()}_csv"])
    _annotate_changes(result["rows"], previous_rows)
    write_csv(paths[f"hourly_mot_{flow.lower()}_csv"], HOURLY_MOT_COLUMNS, result["rows"])
    payload = {key: value for key, value in result.items() if key != "rows"}
    paths[f"hourly_mot_{flow.lower()}_json"].write_text(
        json.dumps({**payload, "rows": result["rows"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return paths


def _saved_flow_rows(output_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for flow in SUPPORTED_MOT_FLOWS:
        path = output_dir / f"hourly_mot_{flow}.csv"
        for row in read_csv_rows(path):
            row["flow"] = str(row.get("flow", flow) or flow).upper()
            rows.append(row)
    return rows


def _rollup_paths(output_dir: Path) -> dict[str, Path]:
    mot_dir = output_dir / "mot"
    return {
        "mot_rollup_latest_csv": mot_dir / "mot_rollup_latest.csv",
        "mot_rollup_latest_json": mot_dir / "mot_rollup_latest.json",
        "mot_rollup_latest_md": mot_dir / "mot_rollup_latest.md",
        "mot_latest_csv": mot_dir / "mot_latest.csv",
        "mot_latest_json": mot_dir / "mot_latest.json",
        "mot_latest_md": mot_dir / "mot_latest.md",
        "mot_history_jsonl": mot_dir / "mot_history.jsonl",
        "mot_worklist_csv": mot_dir / "mot_worklist.csv",
        "mot_retest_queue_csv": mot_dir / "mot_retest_queue.csv",
        "hourly_mot_latest_md": output_dir / "hourly_mot_latest.md",
    }


def _write_mot_rollup_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mot_dir = output_dir / "mot"
    mot_dir.mkdir(parents=True, exist_ok=True)
    paths = _rollup_paths(output_dir)
    result["quiet_autonomy_active"] = quiet_autonomy_active(_root_from_output_dir(output_dir))
    previous_worklist = read_csv_rows(paths["mot_worklist_csv"])
    worklist_rows = build_mot_worklist(result, previous_worklist=previous_worklist)
    retest_rows = build_retest_queue(worklist_rows, str(result.get("observed_utc", "")))
    active_work_count = len([row for row in worklist_rows if row.get("status") in MOT_ACTIVE_WORK_STATUSES])
    summary_payload = {key: value for key, value in result.items() if key != "rows"}
    summary_payload["worklist_count"] = active_work_count
    summary_payload["retest_count"] = len(retest_rows)
    summary_payload["output_dir"] = str(mot_dir)

    write_csv(paths["mot_rollup_latest_csv"], HOURLY_MOT_COLUMNS, result["rows"])
    write_csv(paths["mot_latest_csv"], HOURLY_MOT_COLUMNS, result["rows"])
    write_csv(paths["mot_worklist_csv"], MOT_WORKLIST_COLUMNS, worklist_rows)
    write_csv(paths["mot_retest_queue_csv"], MOT_RETEST_QUEUE_COLUMNS, retest_rows)
    rollup_json = json.dumps({**summary_payload, "rows": result["rows"]}, indent=2) + "\n"
    paths["mot_rollup_latest_json"].write_text(rollup_json, encoding="utf-8")
    paths["mot_latest_json"].write_text(rollup_json, encoding="utf-8")
    markdown = build_hourly_mot_markdown(result, worklist_rows)
    paths["mot_rollup_latest_md"].write_text(markdown, encoding="utf-8")
    paths["mot_latest_md"].write_text(markdown, encoding="utf-8")
    paths["hourly_mot_latest_md"].write_text(markdown, encoding="utf-8")
    with paths["mot_history_jsonl"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary_payload, sort_keys=True) + "\n")
    return paths


def _root_from_output_dir(output_dir: Path) -> Path:
    try:
        return output_dir.resolve().parents[2]
    except IndexError:
        return output_dir.resolve()


def write_hourly_mot_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mot_dir = output_dir / "mot"
    mot_dir.mkdir(parents=True, exist_ok=True)
    flow = str(result.get("flow", "A")).upper()
    if flow == "ALL":
        return _write_mot_rollup_outputs(result, output_dir)

    paths = _write_single_flow_mot_outputs(result, output_dir)
    rollup_rows = _saved_flow_rows(output_dir)
    rollup_result = build_mot_rollup_result(rollup_rows, observed_utc=str(result.get("observed_utc", "")))
    paths.update(_write_mot_rollup_outputs(rollup_result, output_dir))
    return paths


def write_all_hourly_mot_outputs(results: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "mot").mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for result in results:
        paths.update(_write_single_flow_mot_outputs(result, output_dir))
    rollup_rows = _saved_flow_rows(output_dir)
    observed = _latest_row_observed_utc(rollup_rows) or utc_now_text()
    rollup_result = build_mot_rollup_result(rollup_rows, observed_utc=observed)
    paths.update(_write_mot_rollup_outputs(rollup_result, output_dir))
    return paths
