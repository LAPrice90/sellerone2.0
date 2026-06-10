# Execution Batch 010 - H004 Market Snapshot SQL Pilot

Date: 2026-04-28
Status: runtime verification passed

## Goal
- Start H-flow migration with a local market-intelligence output, without touching repricing execution or publish writes.

## Scope
- Datasets:
  - `H.HOS_DAILY_MARKET_SNAPSHOT_LATEST`
  - `H.HOS_DAILY_MARKET_HISTORY`
- Existing CSV exports:
  - `out/hos_daily_market_snapshot_<date>.csv`
  - `out/hos_daily_market_snapshot_latest.csv`
  - `out/hos_daily_market_history.csv`
- SQL tables:
  - `h_hos_daily_market_snapshot`
  - `h_hos_daily_market_history`

## Allowed Changes
- `scripts/flows/H/H004_build_daily_market_snapshot.py`
- `tests/test_h004_build_daily_market_snapshot.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- In SQL-primary mode, both SQL tables are replaced in one transaction before CSV exports are written.
- Do not change repricing decision, write, publish, or scheduler ownership code in this batch.
- Do not restart schedulers or live loops during this batch.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_h004_build_daily_market_snapshot.py tests/test_storage_adapter.py`

## Runtime Proof
- Use direct local H004 proof only against current local market snapshots.
- H scheduler remains paused; no repricing controlled run is required because this batch does not touch the H pricing loop.

## Result
- Code fix applied: yes - `H004_build_daily_market_snapshot.py` now supports SQL-primary local market snapshot/history outputs.
- Isolated verification passed: yes - `python -m pytest tests/test_h004_build_daily_market_snapshot.py tests/test_storage_adapter.py` passed 8 tests; broader migration regression command passed 28 tests.
- Runtime verification: passed - direct local H004 proof ran with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`; SQL table `h_hos_daily_market_snapshot` row count `65` matched `out/hos_daily_market_snapshot_latest.csv` row count `65`; SQL table `h_hos_daily_market_history` row count `162` matched `out/hos_daily_market_history.csv` row count `162`.
