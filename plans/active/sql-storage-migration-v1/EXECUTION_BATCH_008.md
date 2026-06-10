# Execution Batch 008 - A006 Stock Events SQL Pilot

Date: 2026-04-28
Status: runtime verification passed

## Goal
- Start A-flow migration with a low-risk local output that does not require API or Sheet activity for proof.

## Scope
- Dataset: `A.STOCK_EVENTS_RAW`
- Existing CSV export: `out/stock_events_raw.csv`
- SQL table: `a_stock_events_raw`

## Allowed Changes
- `scripts/flows/A/A006_build_stock_events_raw.py`
- `tests/test_a006_build_stock_events_raw.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- In SQL-primary mode, SQL write must complete before CSV export.
- Sheet writes are gated by `A006_WRITE_SHEETS`; proof runs use `A006_WRITE_SHEETS=0`.
- Do not restart schedulers or live loops during this batch.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_a006_build_stock_events_raw.py tests/test_storage_adapter.py`

## Runtime Proof
- Use local A006 script proof only, with Sheets disabled.
- Do not run a full A cycle or standalone A015 for this batch unless explicitly needed for owned A proof later.

## Result
- Code fix applied: yes - `A006_build_stock_events_raw.py` now supports SQL-primary local output and a proof-only Sheet gate.
- Isolated verification passed: yes - `python -m pytest tests/test_a006_build_stock_events_raw.py tests/test_storage_adapter.py` passed 8 tests; broader migration regression command passed 26 tests.
- Runtime verification: passed - `A006_build_stock_events_raw.py` ran with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `A006_WRITE_SHEETS=0`, and wrote SQL table `a_stock_events_raw` row count `6033`; CSV export `out/stock_events_raw.csv` row count also `6033`.
