# Execution Batch 026 - Product DB Preview SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand shared Product DB preview output to SQL-primary storage across all current producers without running API or Sheet-writing flows.

## Scope
- Registered dataset:
  - `SYS.PRODUCT_DB_PREVIEW`
- Compatibility CSV export:
  - `out/product_db_preview.csv`
- SQL table:
  - `sys_product_db_preview`

## Allowed Changes
- `scripts/core/storage/pandas_bridge.py`
- `scripts/core/storage/__init__.py`
- `scripts/flows/A/A001_run_listings_to_sheet.py`
- `scripts/flows/A/A002_run_catalog_items_to_sheet.py`
- `scripts/flows/A/A003_run_inventory_to_sheet.py`
- `scripts/flows/A/A004_run_fees_to_sheet.py`
- `scripts/flows/B/B001_run_orders_to_sheet.py`
- `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
- `scripts/flows/B/B003_run_financial_events_level3.py`
- `tests/test_storage_adapter.py`
- `tests/test_product_db_preview_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run Product DB producer flows for storage proof, because they can call SP-API and/or write Google Sheets.
- Convert all current Product DB preview producers so the shared output cannot fall back to CSV-only depending on producer path.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_product_db_preview_storage.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local Product DB preview through the shared SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_product_db_preview_storage.py tests/test_inbound_shipment_contents_storage.py tests/test_process_stock_receipts_sheet.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - all seven current producers for `out/product_db_preview.csv` now use SQL-compatible writing.
- Shared helper added: `write_dataframe_with_sql_compat` centralizes the SQL-primary then CSV compatibility export pattern for repeated shared outputs.
- Isolated verification passed: yes - focused Product DB/storage tests passed 10 tests.
- Guarded local storage verification passed: yes - SQL row count matched CSV row count:
  - `sys_product_db_preview`: SQL `608`, CSV `608`, columns `72`
- Broad migration regression passed: yes - broad SQL migration regression passed 77 tests with `PYTHONPATH` set to the repo root.
- Full producer proof not run for this batch: running the producer flows can call SP-API and/or write Google Sheets, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1258` CSV calls, `173` registered dependencies, `112` SQL-primary pilot-proven calls, `69` remaining registered CSV dependencies, `800` unresolved dynamic calls, and `285` unregistered CSV calls.
