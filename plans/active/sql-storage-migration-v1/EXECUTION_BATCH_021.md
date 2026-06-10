# Execution Batch 021 - B003 Financial Events Level 3 Official SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand B-flow SQL-primary coverage to the official Level 3 financial-events artifact without running the SP-API financial-events pull during migration proof.

## Scope
- Registered dataset:
  - `B.FINANCIAL_EVENTS_LEVEL3_OFFICIAL`
- Compatibility CSV export:
  - `out/financial_events_level3_official.csv`
- SQL table:
  - `b_financial_events_level3_official`

## Allowed Changes
- `scripts/flows/B/B003_run_financial_events_level3.py`
- `tests/test_b003_run_financial_events_level3.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run the full B003 collector for storage proof, because it can call SP-API and write Google Sheets/Product_DB side effects.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b003_run_financial_events_level3.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded the current existing official Level 3 artifact through the new B003 SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Result
- Code fix applied: yes - B003 official output now supports SQL-primary mode.
- Isolated verification passed: yes - focused B003/storage tests passed 9 tests.
- Guarded local storage verification passed: yes - SQL table `b_financial_events_level3_official` row count `10155` matched `out/financial_events_level3_official.csv` row count `10155`.
- Broad migration regression passed: yes - broad SQL migration regression passed 58 tests with `PYTHONPATH` set to the repo root.
- Full B003 proof not run for this batch: running B003 can call SP-API and write Sheet/Product_DB side effects, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1271` CSV calls, `187` registered dependencies, `94` SQL-primary pilot-proven calls, `101` remaining registered CSV dependencies, `796` unresolved dynamic calls, and `288` unregistered CSV calls.
