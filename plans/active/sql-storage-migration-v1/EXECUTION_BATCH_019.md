# Execution Batch 019 - B008 Refund Token Events SQL Expansion

Date: 2026-04-28
Status: guarded local storage verification passed

## Goal
- Expand B-flow SQL-primary coverage to the refund token event log without applying pending refunds to the live token ledger during migration proof.

## Scope
- Registered dataset:
  - `B.REFUND_TOKEN_EVENTS`
- Compatibility CSV export:
  - `out/refund_token_events.csv`
- SQL table:
  - `b_refund_token_events`

## Allowed Changes
- `scripts/flows/B/B008_apply_refunds_to_tokens.py`
- `tests/test_b008_apply_refunds_to_tokens.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- This batch does not migrate `token_ledger_live`; B008 can still update that CSV through the existing compatibility writer.
- Do not run full B008 on current artifacts only to prove storage if unapplied refunds would mutate the token ledger.

## Verification
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b008_apply_refunds_to_tokens.py tests/test_storage_adapter.py`
- Guarded runtime preflight:
  - Current refund source had `191` refund rows.
  - Current refund event log had `19` unique applied event ids.
  - `172` refund rows were not yet in the event log.
  - Full B008 was not run because it would apply pending refunds to the token ledger.
- Guarded storage proof:
  - Seeded the current existing refund event log through the new B008 SQL/CSV writer helper with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Result
- Code fix applied: yes - B008 now writes one combined refund event log instead of overwriting then appending duplicate new rows; SQL-primary mode writes `b_refund_token_events` before the CSV export.
- Isolated verification passed: yes - focused B008/storage tests passed 9 tests.
- Guarded local storage verification passed: yes - SQL table `b_refund_token_events` row count `19` matched `out/refund_token_events.csv` row count `19`.
- Broad migration regression passed: yes - broad SQL migration regression passed 52 tests with `PYTHONPATH` set to the repo root.
- Safety recovery performed: an early test harness mistake wrote a one-row fixture to `out/token_ledger_live.csv` and `out/systems/B/live/token_ledger_live.csv`; both files were restored immediately from the verified migration backup to `13594` rows before continuing.
- Full B008 proof not run for this batch: running B008 would apply `172` pending refund rows to the token ledger, which is a business mutation outside this storage-only proof.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1272` CSV calls, `189` registered dependencies, `84` SQL-primary pilot-proven calls, `113` remaining registered CSV dependencies, `795` unresolved dynamic calls, and `288` unregistered CSV calls.
