# Execution Batch 028 - Token Live Files SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand live token ledger and token allocation outputs to SQL-primary storage without running token mutation one-off scripts.

## Scope
- Registered datasets:
  - `B.TOKEN_LEDGER_LIVE`
  - `B.TOKEN_ALLOCATIONS_LIVE`
- Compatibility CSV exports:
  - `out/token_ledger_live.csv`
  - `out/token_allocations_live.csv`
- SQL tables:
  - `b_token_ledger_live`
  - `b_token_allocations_live`

## Allowed Changes
- `scripts/one_off/T002_B015_fix_duplicate_token_ids.py`
- `scripts/one_off/T009_B031_backfill_tokens_from_orders_sheet.py`
- `scripts/one_off/T010_B034_full_rebuild_tokens_from_orders_sheet.py`
- `tests/test_b_token_live_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run token mutation one-offs for storage proof, because they can change token ledger/allocation truth.
- Prove this batch by seeding the current local files and checking token ledger row counts remain unchanged.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b_token_live_storage.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local token live artifacts through the shared SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b_token_live_storage.py tests/test_b_orders_archive_storage.py tests/test_product_db_preview_storage.py tests/test_inbound_shipment_contents_storage.py tests/test_process_stock_receipts_sheet.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - current registered one-off writers for `out/token_ledger_live.csv` and `out/token_allocations_live.csv` now support SQL-primary mode.
- Isolated verification passed: yes - focused token live/storage tests passed 11 tests.
- Guarded local storage verification passed: yes - SQL row counts matched CSV row counts:
  - `b_token_ledger_live`: SQL `13594`, CSV `13594`, columns `31`
  - `b_token_allocations_live`: SQL `11813`, CSV `11813`, columns `10`
- Broad migration regression passed: yes - broad SQL migration regression passed 83 tests with `PYTHONPATH` set to the repo root.
- Mutation proof not run for this batch: token mutation one-offs were not executed.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1248` CSV calls, `163` registered dependencies, `155` SQL-primary pilot-proven calls, `16` remaining registered CSV dependencies, `800` unresolved dynamic calls, and `285` unregistered CSV calls.
- Remaining registered CSV dependencies are read-only references, not registered writer/export calls.
