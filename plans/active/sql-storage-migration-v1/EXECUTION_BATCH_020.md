# Execution Batch 020 - B009 Stock Adjustment Token Events SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand B-flow SQL-primary coverage to the stock-adjustment token event log without applying pending stock-adjustment actions to the live token ledger during migration proof.

## Scope
- Registered dataset:
  - `B.STOCK_ADJUSTMENT_TOKEN_EVENTS`
- Compatibility CSV export:
  - `out/stock_adjustment_token_events.csv`
- SQL table:
  - `b_stock_adjustment_token_events`

## Allowed Changes
- `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py`
- `tests/test_b009_apply_stock_adjustments_to_tokens.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- This batch does not migrate `token_ledger_live`.
- Do not run full B009 on current artifacts only to prove storage if pending stock-adjustment actions would mutate the token ledger.
- Preserve repeated `event_id` rows because the current historical event log uses repeated ids across different SKU rows.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_storage_adapter.py`
- Guarded runtime preflight:
  - Current stock event source had `250` valid stock-adjustment base event ids.
  - Current stock-adjustment event log had `14096` rows and repeated `event_id` values by design.
  - `246` valid source base event ids were not yet applied in the event log.
  - Full B009 was not run because it would apply pending stock-adjustment actions to the token ledger.
- Guarded storage proof:
  - Seeded the current existing stock-adjustment event log through the new B009 SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Result
- Code fix applied: yes - B009 stock-adjustment event log now supports SQL-primary mode.
- Isolated verification passed: yes - focused B009/storage tests passed 11 tests.
- Guarded local storage verification passed: yes - SQL table `b_stock_adjustment_token_events` row count `14096` matched `out/stock_adjustment_token_events.csv` row count `14096`.
- Broad migration regression passed: yes - broad SQL migration regression passed 56 tests with `PYTHONPATH` set to the repo root.
- Full B009 proof not run for this batch: running B009 would apply `246` pending stock-adjustment base events to the token ledger, which is a business mutation outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1271` CSV calls, `188` registered dependencies, `89` SQL-primary pilot-proven calls, `107` remaining registered CSV dependencies, `795` unresolved dynamic calls, and `288` unregistered CSV calls.
