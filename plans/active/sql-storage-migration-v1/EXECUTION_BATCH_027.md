# Execution Batch 027 - B Order Archive SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand B order and order-item archive outputs to SQL-primary storage without running live order collectors or backfill jobs.

## Scope
- Registered datasets:
  - `B.ORDERS_ALL`
  - `B.ORDER_ITEMS_ALL`
- Compatibility CSV exports:
  - `out/orders_all.csv`
  - `out/order_items_all.csv`
- SQL tables:
  - `b_orders_all`
  - `b_order_items_all`

## Allowed Changes
- `scripts/flows/B/B001_run_orders_to_sheet.py`
- `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
- `scripts/one_off/T019_D020_backfill_missing_orders_from_sellerboard.py`
- `tests/test_b_orders_archive_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run live order collection or Sellerboard backfill for storage proof, because those paths call SP-API and can mutate archive files.
- Convert all current registered writers for `orders_all.csv` and `order_items_all.csv` so the shared archive cannot fall back to CSV-only depending on writer path.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b_orders_archive_storage.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local order archive artifacts through the shared SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b_orders_archive_storage.py tests/test_product_db_preview_storage.py tests/test_inbound_shipment_contents_storage.py tests/test_process_stock_receipts_sheet.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - current registered writers for `out/orders_all.csv` and `out/order_items_all.csv` now support SQL-primary mode.
- Isolated verification passed: yes - focused B order archive/storage tests passed 11 tests.
- Guarded local storage verification passed: yes - SQL row counts matched CSV row counts:
  - `b_orders_all`: SQL `10451`, CSV `10451`, columns `28`
  - `b_order_items_all`: SQL `10473`, CSV `10473`, columns `51`
- Broad migration regression passed: yes - broad SQL migration regression passed 80 tests with `PYTHONPATH` set to the repo root.
- Full producer proof not run for this batch: running order collectors/backfills can call SP-API and mutate archive files, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1253` CSV calls, `168` registered dependencies, `149` SQL-primary pilot-proven calls, `27` remaining registered CSV dependencies, `800` unresolved dynamic calls, and `285` unregistered CSV calls.
