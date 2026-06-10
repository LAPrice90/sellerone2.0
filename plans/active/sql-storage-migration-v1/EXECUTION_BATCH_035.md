# Execution Batch 035 - Live Scheduler Restoration

Started: 2026-04-28T16:45:00Z

## Goal
- Return active scheduler ownership after SQL-primary isolated proofs.
- Keep the active entrypoints in SQL-primary-with-CSV-export mode.
- Avoid restoring reboot-capable or legacy-path scheduler tasks without separate explicit reboot/legacy approval.

## Scope
- `run_A_all.bat`
- `run_B_cycle.bat`
- `run_H_cycle.bat`
- Windows scheduled tasks:
  - `AMZ Orders`
  - `AMZ H Cycle`
  - `AMZ Pricing Summary`
- H controlled mode marker.
- Runtime owner locks and live status artifacts.

## Entry Point Cutover
- `run_A_all.bat` now defaults `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- `run_B_cycle.bat` now defaults `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- `run_H_cycle.bat` now defaults `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- All three default `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`.

## Restore Boundary
- Restore active non-reboot tasks only:
  - `AMZ Orders`
  - `AMZ H Cycle`
  - `AMZ Pricing Summary`
- Do not restore these in this batch:
  - `AMZ Controlled Restart` - reboot-capable.
  - `AMZ Restart Postcheck` - restart controller path.
  - `AMZ Pricing Summary Hourly` - points at legacy `SELLER~1.0` path.

## Stop Conditions
- Any duplicate owner process.
- Any A, B, or H lock conflict.
- Any SQL/CSV rollback export mismatch after restoration.
- Any scheduled task points at an unexpected repo path.
- Any evidence that the restored task starts in CSV mode instead of SQL-primary mode.

## Status
- code fix applied: yes - active A/B/H batch entrypoints now default to SQL-primary storage.
- scheduler restoration applied: yes - `AMZ Orders`, `AMZ H Cycle`, and `AMZ Pricing Summary` are enabled. `AMZ Controlled Restart`, `AMZ Restart Postcheck`, and `AMZ Pricing Summary Hourly` remain disabled by design.
- B live loop verification confirmed: yes - restored owner started from `AMZ Orders`; cycle `B_20260428T164227Z` finalized at `2026-04-28T16:56:29Z` with `final_state=completed`, 12/12 launched steps completed, and split health written. A second restored cycle `B_20260428T165629Z` also finalized at `2026-04-28T17:00:43Z`, and the supervisor immediately started the next cycle.
- B known scoped health state: `1 FAIL` (`token_shortages_by_sku`) and `1 WARN` (`order_master_placeholder_cogs_rows`) remained after the restored cycles. These are existing B-flow data/health conditions, not SQL cutover or ownership restoration failures.
- H live loop verification confirmed: yes - H controlled mode was cleared through isolation tooling, `AMZ H Cycle` resumed, first restored continuous production run `20260428T164339Z` finalized, `H_last_finalized_run_id.txt` updated to `20260428T164339Z`, publish status was `ok`, and the owner immediately started the next continuous production run `20260428T170156Z`.
- A scheduler restoration confirmed: yes - `AMZ Pricing Summary` is enabled with next run `29/04/2026 06:00:00` local time. No duplicate A run was forced after the isolated A proof.
- active disabled tasks retained: `AMZ Controlled Restart`, `AMZ Restart Postcheck`, and `AMZ Pricing Summary Hourly`.
- recorded at: 2026-04-28T17:03:30Z.
