# Execution Batch 014 - E006/E007 Sales Truth SQL Expansion

Date: 2026-04-28
Status: runtime verification passed

## Goal
- Expand E-flow SQL-primary coverage through the sales truth reconciliation and daily sales truth writers.

## Scope
- Compatibility CSV exports:
  - `out/sales_truth_sku_30d_latest.csv`
  - `out/sales_truth_reconciliation_latest.csv`
  - `out/sku_daily_sales_truth_latest.csv`
- SQL tables:
  - `e_sales_truth_sku_30d`
  - `e_sales_truth_reconciliation`
  - `e_sku_daily_sales_truth`

## Allowed Changes
- `scripts/flows/E/E006_build_sales_truth_reconciliation.py`
- `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- `tests/test_e006_build_sales_truth_reconciliation.py`
- `tests/test_e007_build_sku_daily_sales_truth.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- E publish remains disabled for proof with `E_WRITE_SHEETS=0`.
- Existing CSV exports stay in place for compatibility and proof.

## Verification
- Focused isolated command:
  - `pytest tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_storage_adapter.py`
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`
- Runtime proof:
  - Owned E cycle with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `E_WRITE_SHEETS=0`, and `E_ENFORCE_CADENCE=0`.

## Result
- Code fix applied: yes - `E006_build_sales_truth_reconciliation.py` now writes both sales truth SQL tables transactionally before CSV compatibility exports in SQL-primary mode; `E007_build_sku_daily_sales_truth.py` writes its daily truth SQL table before CSV compatibility export in SQL-primary mode.
- Isolated verification passed: yes - focused E006/E007/storage tests passed 17 tests.
- Broad migration regression passed: yes - broad SQL migration regression passed 38 tests with `PYTHONPATH` set to the repo root.
- Runtime verification: passed - owned E cycle ran with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `E_WRITE_SHEETS=0`, and `E_ENFORCE_CADENCE=0`; E split health reported `0 FAIL` and `0 WARN`.
- Row-count proof: `e_sales_truth_sku_30d` `57` matched `out/sales_truth_sku_30d_latest.csv` `57`; `e_sales_truth_reconciliation` `57` matched `out/sales_truth_reconciliation_latest.csv` `57`; `e_sku_daily_sales_truth` `454` matched `out/sku_daily_sales_truth_latest.csv` `454`.
- Pause proof after run: scheduled migration-controlled tasks remained disabled and no Python owner process remained after verification.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1279` CSV calls, `37` SQL-primary pilot-proven calls, `169` remaining registered CSV dependencies, `793` unresolved dynamic calls, and `288` unregistered CSV calls.
