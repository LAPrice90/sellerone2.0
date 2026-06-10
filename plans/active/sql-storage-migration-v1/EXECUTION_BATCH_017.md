# Execution Batch 017 - B004 Order Master SQL Expansion

Date: 2026-04-28
Status: local runtime verification passed

## Goal
- Expand B-flow SQL-primary coverage to the main B004 order-master output.

## Scope
- Registered dataset:
  - `B.ORDER_MASTER`
- Compatibility CSV export:
  - `out/order_master.csv`
- SQL table:
  - `b_order_master`

## Allowed Changes
- `scripts/flows/B/B004_build_order_master.py`
- `tests/test_b004_level_gate.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- `out/order_master_prev.csv` snapshot behavior is preserved before the main export is replaced.
- SKU-filter preview output remains CSV-only because it is not the registered master table.
- Runtime proof uses `ORDER_MASTER_SKIP_SHEETS=1` and `B_CYCLE_QUIET=1`.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b004_level_gate.py tests/test_storage_adapter.py`
- Local runtime proof:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
  - `ORDER_MASTER_SKIP_SHEETS=1`
  - `B_CYCLE_QUIET=1`
  - `ORDER_MASTER_L1_STABLE_SECONDS=0`
  - `python scripts/flows/B/B004_build_order_master.py`
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Result
- Code fix applied: yes - B004 now writes `b_order_master` before exporting `out/order_master.csv` in SQL-primary mode.
- Isolated verification passed: yes - focused B004/storage tests passed 15 tests.
- Local runtime verification passed: yes - B004 ran with SQL-primary mode and Sheet writes disabled.
- Row-count proof: `b_order_master` `10183` matched `out/order_master.csv` `10183`; related B004 diagnostic outputs still matched their CSV exports.
- Existing B004 warnings observed during proof: `source_duplicate_keys_collapsed`, `l1_missing_fees_observed`, `missing_token_cogs_observed`, and `l2_not_viable_fallback_to_l1`. These were existing data-quality outputs from the order-master build and did not block SQL/CSV reconciliation.
- Broad migration regression passed: yes - broad SQL migration regression passed 48 tests with `PYTHONPATH` set to the repo root.
- Full B-cycle proof not run for this batch: the direct B004 run proved the local B004 output without widening into B cycle API/Sheet-capable steps.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1276` CSV calls, `194` registered dependencies, `65` SQL-primary pilot-proven calls, `137` remaining registered CSV dependencies, `794` unresolved dynamic calls, and `288` unregistered CSV calls.
