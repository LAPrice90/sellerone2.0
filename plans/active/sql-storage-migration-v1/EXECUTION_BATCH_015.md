# Execution Batch 015 - B012 Token Events SQL Expansion

Date: 2026-04-28
Status: local runtime verification passed

## Goal
- Expand B-flow SQL-primary coverage to the append-only token events output without changing Sheet behavior.

## Scope
- Registered dataset:
  - `B.TOKEN_EVENTS`
- Compatibility CSV export:
  - `out/token_events.csv`
- SQL table:
  - `b_token_events`

## Allowed Changes
- `scripts/flows/B/B012_build_token_events_append.py`
- `tests/test_b012_build_token_events_append.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes the full event log to SQL before exporting the CSV compatibility file.
- Sheet writes remain disabled by default with `TOKEN_EVENTS_WRITE_SHEETS=0`.
- The existing append-only behavior remains unchanged in default CSV mode.

## Verification
- Focused isolated command:
  - `pytest tests/test_b012_build_token_events_append.py tests/test_storage_adapter.py`
- Local runtime proof:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
  - `TOKEN_EVENTS_WRITE_SHEETS=0`
  - `python scripts/flows/B/B012_build_token_events_append.py`
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Result
- Code fix applied: yes - B012 now supports SQL-primary mode for the full token event log and keeps CSV mode append behavior unchanged.
- Isolated verification passed: yes - focused B012/storage tests passed 9 tests.
- Local runtime verification passed: yes - B012 ran with SQL-primary mode and Sheet writes disabled; SQL table `b_token_events` row count `92644` matched `out/token_events.csv` row count `92644`.
- Broad migration regression passed: yes - broad SQL migration regression passed 40 tests with `PYTHONPATH` set to the repo root.
- Full B-cycle proof not run for this batch: B012 is not in the current `scripts/cycles/run_B_cycle.py` run order, so a full `B_RUN_ONCE` would not prove this script and would widen scope into API/Sheet-capable steps.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1282` CSV calls, `201` registered dependencies, `47` SQL-primary pilot-proven calls, `162` remaining registered CSV dependencies, `793` unresolved dynamic calls, and `288` unregistered CSV calls.
