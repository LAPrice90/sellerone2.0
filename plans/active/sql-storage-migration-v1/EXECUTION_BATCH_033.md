# Execution Batch 033 - H-Owned Controlled SQL-Primary Proof

Started: 2026-04-28T15:12:36Z

## Goal
- Run the H controlled proof path under `sql_primary_csv_export`.
- Keep scheduler ownership paused.
- Keep Google Sheets publish disabled.
- Keep live price writes disabled.
- Use the H isolation tooling to reconcile stale H run markers instead of deleting markers manually.

## Scope
- `out/sql/sellerone_dev.sqlite3`
- H-owned local CSV compatibility exports.
- `out/systems/H/live/*`
- H logs, H scoped health outputs, and SQL migration rollback proof artifacts.
- `plans/active/sql-storage-migration-v1/*`

## Preflight Evidence
- AMZ scheduled tasks are disabled, including `AMZ H Cycle`.
- No live `python.exe` owner process was present at the H preflight.
- H live marker `out/systems/H/live/H_run_in_progress.txt` existed with stale run id `20260428T121555Z`.
- `out/systems/H/live/H_run_state.json` still showed stale owner pid `21076`, stage `phase1_pilot`.
- `plans/active/sql-storage-migration-v1/forced_proof_H.json` reported `stale_marker_review_required`.

## Proof Boundary
- Run `run_H_isolation_pause.bat` first to enter controlled mode and reconcile ownership safely.
- Run `run_H_isolation_success.bat` only after controlled mode is active, the scheduler is disabled, and no H owner process is live.
- Run with:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
  - `H_STAGE_PHASE1_PUBLISH=0`
  - `H_PHASE1_OBSERVATION_PUBLISH_ENABLED=0`
  - `H_PHASE1_OBSERVATION_STATUS_PUBLISH_ENABLED=0`
  - `H_PHASE1_OBSERVATION_STATUS_PUBLISH_ON_START=0`
  - `H_PHASE1_OBSERVATION_STATUS_PUBLISH_ON_ERROR=0`
  - `H_PHASE_ENGINE_LIVE_WRITES=0`
  - `H_LIVE_WRITE=0`
  - `H_ALLOW_NO_PUBLISH_TERMINAL_OK=1`
- Final controlled proof used H snapshot and item-offer collection stages so freshness checks could be proven, while keeping Sheet publish and live price writes disabled.

## Stop Conditions
- Any Google Sheets write attempt.
- Any live price write attempt.
- H controlled proof fails before terminal markers.
- H scoped health has a new `FAIL`.
- SQL rollback export validation fails for any mapped table.

## Status
- code fix applied: yes - fixed two H writers that were still bypassing SQL compatibility:
  - `h_seller_profiles` / `h_seller_of_interest`
  - `h_listing_offer_history`
- isolated verification passed: yes.
- live loop verification: not yet proven for scheduler restoration. Scheduler ownership remains paused by design.

## Proof Evidence
- `python -m py_compile scripts\cycles\run_H_pricing_cycle.py` passed.
- Focused storage tests passed: `12 passed`.
- First H proof archived stale run marker `20260428T121555Z` through isolation tooling.
- Final H controlled proof run id: `20260428T160125Z`.
- Final H run state: `finalized`.
- Final H worker state: `succeeded`.
- Final H publish status: `skipped_disabled`.
- Final H status check: `AMZ H Cycle` disabled, controlled mode active, owner process count `0`, no H locks, no run in progress.
- Rollback validation: `48 pass`, `0 fail`, report `out\sql_migration\rollback_exports_20260428T161607Z\rollback_export_report.csv`.
- H scoped health: `0 FAIL`, `4 WARN`.

## Remaining WARNs
- `h_strategy_sample_size_multi_seller_ladder_cap`
- `h_strategy_sample_size_single_rival_reset`
- `h_parked_sku_write_attempts`
- `h_floor_referral_source_coverage`

## Notes
- The H proof did not restore scheduler ownership.
- The H proof did not enable Google Sheets publish.
- The H proof did not enable live price writes.
