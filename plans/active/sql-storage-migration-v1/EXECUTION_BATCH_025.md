# Execution Batch 025 - Inbound Shipment Contents SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand shared inbound shipment contents output to SQL-primary storage without running live SP-API inbound collectors.

## Scope
- Registered dataset:
  - `SYS.INBOUND_SHIPMENT_CONTENTS`
- Compatibility CSV export:
  - `out/inbound_shipment_contents.csv`
- Additional local SQL table:
  - `sys_inbound_shipment_contents_raw` for `out/inbound_shipment_contents_raw.csv`
- SQL tables:
  - `sys_inbound_shipment_contents`
  - `sys_inbound_shipment_contents_raw`

## Allowed Changes
- `scripts/flows/B/B030_run_inbound_shipment_contents_report.py`
- `scripts/flows/B/B031_run_inbound_shipment_items.py`
- `tests/test_inbound_shipment_contents_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Do not run full inbound collectors for storage proof, because they call SP-API report and inbound endpoints.
- Convert both producers that can write `out/inbound_shipment_contents.csv` so the shared output cannot fall back to CSV-only depending on producer path.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_inbound_shipment_contents_storage.py tests/test_storage_adapter.py`
- Guarded storage proof:
  - Seeded current local inbound shipment contents artifacts through the new SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_inbound_shipment_contents_storage.py tests/test_process_stock_receipts_sheet.py tests/test_a005_inventory_adjustments_storage.py tests/test_a004_fee_requeue.py tests/test_b003_run_financial_events_level3.py tests/test_b009_apply_stock_adjustments_to_tokens.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Current Result
- Code fix applied: yes - both inbound shipment contents producers now support SQL-primary mode.
- Isolated verification passed: yes - focused inbound/storage tests passed 10 tests.
- Guarded local storage verification passed: yes - SQL row counts matched CSV row counts:
  - `sys_inbound_shipment_contents`: SQL `47`, CSV `47`, columns `3`
  - `sys_inbound_shipment_contents_raw`: SQL `47`, CSV `47`, columns `3`
- Broad migration regression passed: yes - broad SQL migration regression passed 74 tests with `PYTHONPATH` set to the repo root.
- Full inbound collector proof not run for this batch: running those collectors can call SP-API, which is outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; current summary shows `1264` CSV calls, `180` registered dependencies, `104` SQL-primary pilot-proven calls, `84` remaining registered CSV dependencies, `799` unresolved dynamic calls, and `285` unregistered CSV calls.
