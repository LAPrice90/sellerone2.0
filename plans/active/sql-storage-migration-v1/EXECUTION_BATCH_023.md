# Execution Batch 023 - A005 Inventory Report Outputs SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand A-flow SQL-primary coverage to A005 local inventory report outputs without running the live SP-API report collector.

## Scope
- Registered datasets:
  - `A.INVENTORY_ADJUSTMENTS_LATEST`
  - `A.INVENTORY_LEDGER_RAW`
- Compatibility CSV exports:
  - `out/inventory_adjustments_latest.csv`
  - `out/inventory_ledger_raw.csv`
- Fallback compatibility CSV supported but not currently present:
  - `out/inventory_adjustments_raw.csv`
- SQL tables:
  - `a_inventory_adjustments_latest`
  - `a_inventory_ledger_raw`
  - `a_inventory_adjustments_raw`

## Allowed Changes
- `scripts/flows/A/A005_run_inventory_adjustments_report.py`
- `tests/test_a005_inventory_adjustments_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run full A005 for storage proof, because it can call SP-API report endpoints.
- Do not create missing fallback CSVs just to make proof look complete.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_a005_inventory_adjustments_storage.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local A005 artifacts through the new A005 SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - A005 local inventory report outputs now support SQL-primary mode.
- Isolated verification passed: yes - focused A005/storage tests passed 11 tests.
- Guarded local storage verification passed: yes - SQL row counts matched CSV row counts:
  - `a_inventory_ledger_raw`: SQL `6033`, CSV `6033`
  - `a_inventory_adjustments_latest`: SQL `6033`, CSV `6033`
- Fallback raw adjustments proof: skipped because `out/inventory_adjustments_raw.csv` is not present in the current local state.
- Broad migration regression passed: yes - broad SQL migration regression passed 67 tests with `PYTHONPATH` set to the repo root.
- Full A005 proof not run for this batch: running A005 can call SP-API report endpoints, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1266` CSV calls, `183` registered dependencies, `99` SQL-primary pilot-proven calls, `92` remaining registered CSV dependencies, `796` unresolved dynamic calls, and `287` unregistered CSV calls.
