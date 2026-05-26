# SellerOne 2.0 Architecture Audit

Audit timestamp: 2026-05-01T14:22Z

## Evidence Sources

- Source inventory: `project_control/SCRIPT_INVENTORY.csv`
- Runtime owner contract: `config/runtime_owner_contract.json`
- Scheduler export found: `config/scheduler/AMZ_Price_List_Manager.xml`
- Current proof exports: `out/scanner_latest.csv`, `out/db_snapshot.csv`, `out/link_check.csv`, `out/pricing_output.csv`
- Health snapshots: `out/system_health_checklist.csv`, `out/cycle_alerts/checklist_B.csv`, `out/cycle_alerts/checklist_E.csv`, `out/cycle_alerts/checklist_H.csv`
- Live owner markers: `out/systems/B/live/B_cycle.lock`, `out/H_pricing_cycle.lock`, `out/systems/F/price_list_manager/live/live_cycle.lock`

## Project Inventory Summary

- Source inventory rows: 708
- Python source/test scripts: 669
- Batch entrypoints: 31
- PowerShell helper scripts: 7
- Scheduler XML exports: 1
- Main code folders: `scripts/`, `tests/`, `config/`, `data/`, `out/`, `project_control/`, `plans/`, `reference/`
- Runtime data folders: `out/`, `out/systems/`, `out/cycle_alerts/`, `out/manifests/`, `out/sql/`, `out/logs/`, `data/`

## Entry Points

| Entry point | Owner chain | Evidence |
|---|---|---|
| `run_A_all.bat` | `run_A_all.bat` -> `scripts/cycles/run_A_all.py` | `config/runtime_owner_contract.json` |
| `run_B_cycle.bat` | `run_B_cycle.bat` -> `scripts/cycles/run_B_supervisor.py` -> `scripts/cycles/run_B_cycle.py` | `out/systems/B/live/B_cycle.lock` |
| `run_E_all.bat` | `run_E_all.bat` -> `scripts/cycles/run_E_cycle.py` | `out/systems/E/live/e_run_log.jsonl` |
| `run_H_cycle.bat` | `run_H_cycle.bat` -> `scripts/cycles/run_H_pricing_cycle_guarded.py` -> `scripts/cycles/run_H_pricing_cycle.py` | `out/H_pricing_cycle.lock`, `out/systems/H/live/H_cycle_last_terminal_info.txt` |
| `run_F_price_list_manager_supervisor.bat` | `run_F_price_list_manager_supervisor.bat` -> `scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py` -> `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py` -> `scripts/flows/F/F061_run_legacy_first_checks_local.py` | `out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt` |
| `run_F_price_list_manager_cycle.bat` | Direct F manager runner: `run_F_price_list_manager_cycle.bat` -> `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py` -> `scripts/flows/F/F061_run_legacy_first_checks_local.py` | `out/systems/F/price_list_manager/live/live_cycle_status.csv` |
| `run_O_operator_ui.bat` | `run_O_operator_ui.bat` -> `streamlit run scripts/flows/O/O400_operator_ui.py` | batch file inspection |
| `run_controlled_restart_controller.bat` | `run_controlled_restart_controller.bat` -> `scripts/tools/controlled_restart_controller.py` | batch file inspection |
| `run_api_collection.py` | root Python API collector | source inventory |

## Scheduler-Linked Scripts

| Scheduler task evidence | Script |
|---|---|
| `config/scheduler/AMZ_Price_List_Manager.xml` BootTrigger, `MultipleInstancesPolicy=IgnoreNew` | `run_F_price_list_manager_supervisor.bat` |
| Runtime docs and controller defaults reference `AMZ Orders` | `run_B_cycle.bat` |
| Runtime docs and controller defaults reference `AMZ H Cycle` | `run_H_cycle.bat` |
| Runtime docs and controller defaults reference `AMZ Controlled Restart` | `run_controlled_restart_controller.bat` |

Only the F price-list manager task XML was present in `config/scheduler/` during this audit.

## System Map

### Scanner / Feeder Price List

- System name: F scanner and price-list manager
- Owner scripts:
  - `run_F_price_list_manager_cycle.bat`
  - `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `scripts/flows/F/F005_build_supplier_price_list_universal.py`
  - `scripts/flows/F/F010_build_feeder_candidate_intake.py`
  - `scripts/flows/F/F020_build_feeder_candidate_classification.py`
  - `scripts/flows/F/F030_build_shared_feeder_pass_logic.py`
  - `scripts/flows/F/F040_build_feeder_candidate_approval_queue.py`
- Inputs:
  - Supplier config: `config/feeder/suppliers/*.json`
  - Supplier inbox: `out/systems/F/inbox/`
  - Product DB context: `out/product_db_preview.csv`
  - BBP / web scrape evidence through legacy scanner modules under `scripts/flows/F/legacy_scanner_2_1/`
  - Amazon SP-API pricing/catalog/fees helpers
- Outputs:
  - `out/systems/F/live/feeder_legacy_first_checks_live.csv`
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_candidate_recommendations_live.csv`
  - `out/systems/F/live/feeder_approval_queue_live.csv`
  - Audit export: `out/scanner_latest.csv`
- Dependencies:
  - Feeds O review/listing/Product DB promotion work.
  - Reads Product DB identity/cost context.
  - Uses external Amazon and BBP/web evidence for scanner decisions.

### Database / Product Records

- System name: Product DB local mirror and SQL storage bridge
- Owner scripts:
  - `scripts/flows/A/A001_run_listings_to_sheet.py`
  - `scripts/flows/A/A002_run_catalog_items_to_sheet.py`
  - `scripts/flows/A/A003_run_inventory_to_sheet.py`
  - `scripts/flows/A/A004_run_fees_to_sheet.py`
  - `scripts/flows/B/B003_run_financial_events_level3.py`
  - `scripts/core/storage/pandas_bridge.py`
  - `scripts/core/storage/adapter.py`
  - `scripts/flows/O/O030_build_product_db_operator_view.py`
  - `scripts/flows/O/O430_build_product_db_promotion_candidates.py`
  - `scripts/flows/O/O431_stage_product_db_create_events.py`
  - `scripts/one_off/P014_apply_product_db_edit_events.py`
  - `scripts/one_off/P015_product_db_sql_authority_rehearsal.py`
  - `scripts/one_off/P018_product_db_mirror_drift_guard.py`
  - `scripts/one_off/P019_product_db_reader_dependency_map.py`
  - `scripts/one_off/P020_product_db_postgres_promotion_rehearsal.py`
  - `scripts/one_off/P021_sql_product_db_ui_authority_phase2_signoff.py`
- Inputs:
  - Google Sheet `Product_DB`
  - `out/product_db_preview.csv`
  - SQLite mirror `out/sql/sellerone_dev.sqlite3`
  - F listing/product review outputs
- Outputs:
  - `out/product_db_preview.csv`
  - `out/systems/O/live/product_db_operator_view.csv`
  - SQLite table `sys_product_db_preview`
  - SQLite table `product_db_products`
  - Audit export: `out/db_snapshot.csv`
  - Audit link proof: `out/link_check.csv`
- Dependencies:
  - A/B still update legacy Product DB mirror fields from Amazon/listings/finance evidence.
  - O Product DB view now prefers SQL `product_db_products` when present.
  - P018 classifies stale `out/product_db_preview.csv` as mirror/export evidence, not Product DB authority.
  - P019 maps remaining Product DB readers by owner before A/B/H runtime changes.
  - H reads Product DB for repricing scope, floor, stock, and cost context.
  - O reads Product DB for restock and product operator views.
  - F reads Product DB for listing SKU collision checks and backtest mapping.

### Pricing / ROI / Repricing

- System name: E analytics plus H repricer
- Owner scripts:
  - `scripts/cycles/run_E_cycle.py`
  - `scripts/flows/E/E001_build_sales_velocity.py`
  - `scripts/flows/E/E002_build_roi_snapshot.py`
  - `scripts/flows/E/E003_build_restock_signals.py`
  - `scripts/flows/E/E004_build_performance_summary.py`
  - `run_H_cycle.bat`
  - `scripts/cycles/run_H_pricing_cycle_guarded.py`
  - `scripts/cycles/run_H_pricing_cycle.py`
  - `scripts/flows/H/H110_run_phase1_h_pilot.py`
  - `scripts/flows/H/H130_build_phase1_observation_sheet.py`
  - `scripts/flows/O/O050_build_repricing_tracker_view.py`
  - `scripts/flows/O/O450_repricing_tracker_ui.py`
  - `scripts/one_off/P017_repricing_tracker_ui_parity_check.py`
- Inputs:
  - B order and token outputs: `out/order_master.csv`, `out/token_cogs_ledger.csv`
  - Product DB: `out/product_db_preview.csv`
  - E ROI outputs: `out/sku_roi_snapshot.csv`
  - H market data: `out/listing_offer_snapshot_*.csv`, `out/listing_offer_seller_snapshot_*.csv`
  - Repricing state under `data/`
- Outputs:
  - `out/sku_roi_snapshot.csv`
  - `out/sku_sales_velocity.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `data/decision_log.csv`
  - `data/execution_log.csv`
  - `out/systems/H/live/H_cycle_last_terminal_info.txt`
  - Audit export: `out/pricing_output.csv`
- Dependencies:
  - H depends on fresh A/B/E data and Product DB.
  - H publishes a pricing dashboard through `H130_build_phase1_observation_sheet.py`.
  - E depends on B sales/order/token outputs.

### A Cycle

- System name: A daily data and health cycle
- Owner scripts:
  - `run_A_all.bat`
  - `scripts/cycles/run_A_all.py`
  - `scripts/flows/A/A001_run_listings_to_sheet.py`
  - `scripts/flows/A/A002_run_catalog_items_to_sheet.py`
  - `scripts/flows/A/A003_run_inventory_to_sheet.py`
  - `scripts/flows/A/A004_run_fees_to_sheet.py`
  - `scripts/flows/A/A005_run_inventory_adjustments_report.py`
  - `scripts/flows/A/A006_build_stock_events_raw.py`
  - `scripts/flows/A/A015_build_system_health_check.py`
  - `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
  - `scripts/flows/A/A018_build_phase1_floor_table.py`
- Inputs:
  - Amazon SP-API listing/catalog/inventory/fees/report data
  - Google Sheets where explicit A scripts are designed to sync
  - Product DB local mirror
- Outputs:
  - Product DB/listing/inventory/fee CSVs under `out/`
  - `out/system_health_checklist.csv`
  - flow checklists under `out/cycle_alerts/`
  - A manifests under `out/manifests/A/`
- Dependencies:
  - Feeds H, E, B, and O.
  - Must coordinate maintenance with active B owner before overlapping work.

### B Cycle

- System name: B orders, finance, tokens, and sales loop
- Owner scripts:
  - `run_B_cycle.bat`
  - `scripts/cycles/run_B_supervisor.py`
  - `scripts/cycles/run_B_cycle.py`
  - `scripts/flows/B/B001_run_orders_to_sheet.py`
  - `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
  - `scripts/flows/B/B003_run_financial_events_level3.py`
  - `scripts/flows/B/B004_build_order_master.py`
  - `scripts/flows/B/B006_build_fx_ledgers.py`
  - `scripts/flows/B/B007_allocate_tokens_live.py`
  - `scripts/flows/B/B025_build_token_cogs_ledger.py`
- Inputs:
  - Amazon orders, pending orders, financial events, inbound shipment data
  - Product DB local mirror
  - Token ledger and stock adjustment history
- Outputs:
  - `out/orders_all.csv`
  - `out/order_master.csv`
  - `out/token_ledger_live.csv`
  - `out/token_cogs_ledger.csv`
  - `out/systems/B/live/token_ledger_live.csv`
  - `out/cycle_alerts/checklist_B.csv`
- Dependencies:
  - Feeds E ROI and H pricing floors.
  - A must use maintenance handoff before B-owned proof runs.

### H Cycle

- System name: H repricing runtime
- Owner scripts:
  - `run_H_cycle.bat`
  - `scripts/cycles/run_H_pricing_cycle_guarded.py`
  - `scripts/cycles/run_H_pricing_cycle.py`
  - `scripts/flows/H/H004_build_daily_market_snapshot.py`
  - `scripts/flows/H/H110_run_phase1_h_pilot.py`
  - `scripts/flows/H/H130_build_phase1_observation_sheet.py`
- Inputs:
  - Product DB, A inventory/listing data, B token/COGS data, E ROI outputs
  - Offer snapshots and seller detail outputs
  - `config/pilot_sku.yaml`, `config/h_sku_switches.csv`, `config/phase1_writer_modes.csv`
- Outputs:
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/phase1_sku_scope.csv`
  - `out/h_floor_truth_trace.csv`
  - `out/systems/H/live/H_cycle.log`
  - `out/systems/H/live/H_cycle_last_terminal_info.txt`
  - `out/systems/H/live/H_cycle_last_publish_info.txt`
  - `data/decision_log.csv`
  - `data/execution_log.csv`
- Dependencies:
  - Requires A/B/E/Product DB freshness.
  - Publishes pricing dashboard evidence.

### O Operations Loop

- System name: O operations, restock, PO, receiving, Product DB operator view
- Owner scripts:
  - `scripts/cycles/run_O_cycle.py`
  - `scripts/flows/O/O001_build_restock_source_view.py`
  - `scripts/flows/O/O002_build_restock_recommendations.py`
  - `scripts/flows/O/O003_build_restock_review_queue.py`
  - `scripts/flows/O/O030_build_product_db_operator_view.py`
  - `scripts/flows/O/O100_build_purchase_orders.py`
  - `scripts/flows/O/O200_build_ordered_stock_state.py`
  - `scripts/flows/O/O300_build_send_to_amazon_queue.py`
  - `scripts/flows/O/O400_operator_ui.py`
- Inputs:
  - Product DB
  - B sales and token outputs
  - E ROI and velocity outputs
  - F approved product/listing candidates
- Outputs:
  - `out/systems/O/live/restock_source_view.csv`
  - `out/systems/O/live/restock_recommendations_live.csv`
  - `out/systems/O/live/product_db_operator_view.csv`
  - `out/systems/O/live/purchase_orders_live.csv`
  - `out/systems/O/live/ordered_stock_state.csv`
- Dependencies:
  - Planned operations layer fed by A/B/E/H/F.

### External Integrations

- System name: Amazon, BBP/web evidence, Google Sheets
- Owner scripts:
  - `scripts/api/*.py`
  - `scripts/flows/A/A001_run_listings_to_sheet.py`
  - `scripts/flows/A/A002_run_catalog_items_to_sheet.py`
  - `scripts/flows/A/A003_run_inventory_to_sheet.py`
  - `scripts/flows/A/A004_run_fees_to_sheet.py`
  - `scripts/flows/B/B001_run_orders_to_sheet.py`
  - `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `scripts/flows/H/H130_build_phase1_observation_sheet.py`
- Inputs:
  - Amazon SP-API credentials and reports
  - Google Sheets credentials
  - BBP or web scrape pages/evidence
- Outputs:
  - Local CSV outputs under `out/`
  - Sheet writes when script mode allows
  - API logs under `out/api_call_log.jsonl`
- Dependencies:
  - External proof was not forced during this audit to avoid unintended Sheet/API writes.
