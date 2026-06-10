# Execution Batch 029 - SQL-First Reader Migration

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Convert the remaining registered CSV reader dependencies to SQL-first reads with CSV fallback.

## Scope
- Registered reader datasets:
  - `A.INVENTORY_SUMMARIES`
  - `A.INVENTORY_HISTORY`
  - `B.PHASE1_SKU_SCOPE`
  - `H.LISTING_OFFER_HISTORY`
  - `H.SELLER_OF_INTEREST`
- SQL tables:
  - `a_inventory_summaries`
  - `a_inventory_history`
  - `b_phase1_sku_scope`
  - `h_listing_offer_history`
  - `h_seller_of_interest`

## Allowed Changes
- `scripts/core/storage/pandas_bridge.py`
- `scripts/core/storage/__init__.py`
- reader sites listed in `out/sql_migration/csv_dependency_map.csv`
- `tests/test_storage_adapter.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL reads use SQL first only in SQL-enabled modes, then fall back to CSV.
- No live A015 run was performed.
- No API collectors, Sheet writers, or token mutation scripts were run.

## Verification
- Seeded current local reader source artifacts into SQL with metadata:
  - `a_inventory_summaries`: `339` rows, `24` columns
  - `a_inventory_history`: `23308` rows, `19` columns
  - `b_phase1_sku_scope`: `608` rows, `18` columns
  - `h_listing_offer_history`: `3177` rows, `25` columns
  - `h_seller_of_interest`: `24` rows, `18` columns
- Dependency map:
  - `csv_dependency_remaining_count=0`
- Focused compile check:
  - `python -m py_compile` passed for touched reader/storage files.
- Regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b007_allocate_tokens_live.py tests/test_b_token_live_storage.py tests/test_b_orders_archive_storage.py tests/test_product_db_preview_storage.py tests/test_inbound_shipment_contents_storage.py tests/test_process_stock_receipts_sheet.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - storage now has `read_dataframe_with_sql_fallback` and writer metadata for original CSV column names.
- Isolated verification passed: yes - touched files compile and storage helper tests passed.
- Guarded local storage verification passed: yes - five reader source datasets were seeded into SQL and the dependency map reports `0` remaining registered CSV dependencies.
- Broad migration regression passed: yes - broad SQL migration regression passed `91` tests with `PYTHONPATH` set to the repo root.
- A015 full unit file note: `tests/test_a015_health_check_runtime.py` still has unrelated existing expectation/signature failures and was not used as Batch 029 proof. No live A015 run was performed.
