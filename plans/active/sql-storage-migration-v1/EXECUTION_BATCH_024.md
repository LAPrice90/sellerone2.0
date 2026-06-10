# Execution Batch 024 - Stock Receipts Latest SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand A-owned stock receipt latest output to SQL-primary storage without running the Google Sheets stock receipt processor.

## Scope
- Registered dataset:
  - `A.STOCK_RECEIPTS_LATEST`
- Compatibility CSV export:
  - `out/stock_receipts_latest.csv`
- Additional local SQL table:
  - `a_stock_receipt_summary` for `out/stock_receipt_summary.csv`
- SQL tables:
  - `a_stock_receipts_latest`
  - `a_stock_receipt_summary`

## Allowed Changes
- `scripts/tools/process_stock_receipts_sheet.py`
- `tests/test_process_stock_receipts_sheet.py`
- `scripts/flows/B/B004_build_order_master.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run full stock receipt processing for storage proof, because it reads/writes Google Sheets and can append token ledger rows.
- Empty stock receipt outputs must keep a stable header schema instead of blank headerless CSV files.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_process_stock_receipts_sheet.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local stock receipt summary/latest artifacts through the new SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_process_stock_receipts_sheet.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - stock receipt summary/latest outputs now support SQL-primary mode and stable empty-output headers.
- Isolated verification passed: yes - focused stock receipt/storage tests passed 11 tests.
- Guarded local storage verification passed: yes - SQL row counts matched CSV row counts:
  - `a_stock_receipt_summary`: SQL `0`, CSV `0`, columns `11`
  - `a_stock_receipts_latest`: SQL `0`, CSV `0`, columns `11`
- Broad migration regression passed: yes - broad SQL migration regression passed 71 tests with `PYTHONPATH` set to the repo root.
- Regression support fix: B004 now treats `ORDER_MASTER_L1_STABLE_SECONDS=0` as a disabled stability window, matching the existing test/proof setup and preventing a false recently-modified block.
- Full processor proof not run for this batch: running it can read/write Google Sheets and append token ledger rows, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1265` CSV calls, `182` registered dependencies, `100` SQL-primary pilot-proven calls, `90` remaining registered CSV dependencies, `797` unresolved dynamic calls, and `286` unregistered CSV calls.
