# SQL Migration Re-Enable Proof Plan

Date: 2026-04-28
Status: isolated proof executed, scheduler restoration not executed

## Purpose
- Re-enable paused systems only after rollback/export validation has passed.
- Prove SQL-primary storage does not break each flow before returning scheduler ownership.

## Preconditions
- Scheduled tasks are still disabled:
  - `AMZ Orders`
  - `AMZ H Cycle`
  - `AMZ Pricing Summary`
  - `AMZ Controlled Restart`
- No active Python owner process is running.
- Rollback export validation summary is `passed`.
- Dependency map has `csv_dependency_remaining_count=0`.
- Token ledger row count is unchanged from migration proof baseline:
  - `out/token_ledger_live.csv`: `13594`
  - `out/systems/B/live/token_ledger_live.csv`: `13594`

## Environment For Controlled Proof
- Set:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
- Keep Sheet writes disabled for isolated proof unless the user explicitly approves Sheet writes.
- Keep SP-API collectors disabled unless the specific flow proof requires them and the user approves that live call window.

## Proof Order
1. Export rollback proof
   - Run `scripts/one_off/P007_validate_sql_rollback_exports.py`.
   - Required result: `status=passed`, `fail_count=0`, `missing_csv_count=0`, `missing_table_count=0`.

2. Local SQL reader/writer regression
   - Run the migration regression suite recorded in `EXECUTION_BATCH_030.md`.
   - Required result: all tests pass.

3. B-owned isolated proof
   - Use maintenance ownership first if any B owner is active.
   - Run one boundary-safe B proof cycle only after confirming no overlapping B lock.
   - Required result:
     - B run finalizes.
     - SQL/CSV parity remains true for B core tables.
     - token ledger row count does not move unexpectedly.

4. E-owned isolated proof
   - Run E cycle once with Sheet writes disabled.
   - Required result:
     - E run finalizes.
     - E split health remains `0 FAIL`.
     - SQL/CSV parity remains true for E outputs.

5. H-owned isolated proof
   - Keep scheduler ownership paused.
   - Run guarded H controlled one-shot only.
   - Required result:
     - H controlled run finalizes.
     - H output SQL/CSV parity remains true.
     - No duplicate H owner process remains.

6. A-owned proof
   - Do not run standalone A015 as proof.
   - Run A-owned path only in an approved proof window.
   - Required result:
     - A run finalizes.
     - scoped A health is read only after finalization.
     - SQL/CSV parity remains true for A outputs.

7. Scheduler restoration
   - Re-enable scheduled tasks only after isolated proof for their owned flow passes.
   - After each task is enabled, confirm:
     - scheduler state is `Ready` or equivalent enabled state
     - no duplicate owner process exists
     - next owner run starts only once

## Stop Conditions
- Any rollback export validation failure.
- Any SQL/CSV row or header mismatch.
- Token ledger row count changes outside a planned token mutation proof.
- Any duplicate owner process.
- Any Sheet write requirement without explicit user approval.
- Any evidence that contradicts the current storage migration proof.

## Current Execution State
- This plan has not re-enabled scheduled tasks.
- Sheet writers remained disabled during isolated proof.
- B local proof passed without live API calls or Sheet writes.
- E isolated proof passed with Sheet writes disabled.
- H controlled proof passed with scheduler paused, Sheet publish disabled, and live price writes disabled.
- A isolated proof passed with Sheet writers, A010, A020, and B scheduler recovery disabled.
- Final rollback validation passed `48/48`.
