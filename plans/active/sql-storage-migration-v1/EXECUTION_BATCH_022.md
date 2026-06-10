# Execution Batch 022 - A004 Fee Outputs SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand A-flow SQL-primary coverage to A004 fee output artifacts without running the live SP-API fee collector or writing Google Sheets.

## Scope
- Registered datasets:
  - `A.FEES_LATEST`
  - `A.FEES_FAILED`
- Compatibility CSV exports:
  - `out/fees_latest.csv`
  - `out/fees_failed.csv`
- Additional local SQL table:
  - `a_fees_estimates` for `out/fees_estimates.csv`
- SQL tables:
  - `a_fees_latest`
  - `a_fees_failed`
  - `a_fees_estimates`

## Allowed Changes
- `scripts/flows/A/A004_run_fees_to_sheet.py`
- `tests/test_a004_fee_requeue.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run full A004 for storage proof, because it can call SP-API and write Google Sheets/Product_DB side effects.
- Leave `out/product_db_preview.csv` as CSV-only in this batch because it has multiple remaining writers.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_a004_fee_requeue.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local A004 fee artifacts through the new A004 SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - A004 fee outputs now support SQL-primary mode.
- Isolated verification passed: yes - focused A004/storage tests passed 12 tests.
- Guarded local storage verification passed: yes - SQL row counts matched CSV row counts:
  - `a_fees_estimates`: SQL `88`, CSV `88`
  - `a_fees_latest`: SQL `88`, CSV `88`
  - `a_fees_failed`: SQL `0`, CSV `0`
- Broad migration regression passed: yes - broad SQL migration regression passed 63 tests with `PYTHONPATH` set to the repo root.
- Full A004 proof not run for this batch: running A004 can call SP-API and write Google Sheets/Product_DB side effects, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1269` CSV calls, `185` registered dependencies, `94` SQL-primary pilot-proven calls, `99` remaining registered CSV dependencies, `797` unresolved dynamic calls, and `287` unregistered CSV calls.
