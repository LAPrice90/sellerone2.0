# Agent Rules For New Cycle Storage Cleanup

## Purpose
Every new cycle must clean up after itself. Treat this like adding bins and labels to a new workbench before the workbench starts producing files.

## Required Before A New Cycle Is Complete
- Add every new output family to `project_control/log_housekeeping_registry.json`.
- Declare the owner flow, storage class, target type, keep count, age limit, size limit, cleanup action, and safety blockers.
- Add a schema check for every new CSV, JSON, database, or manifest output.
- Add a flow-end cleanup hook using `python scripts/tools/log_housekeeping.py --flow <FLOW>`.
- Add a storage health alert for any folder that can grow over time.
- Add a rollback rule with a fixed keep count or age limit.
- Add a test proving cleanup does not delete live files, current databases, current publish outputs, or protected rollback files.

## Storage Classes
- `current_runtime`: live files needed by the running system. These must be protected.
- `rollback`: backup or staged folders kept for fast recovery. These must have a fixed keep count.
- `audit_history`: business proof and governance evidence. These are usually protected or archived, not deleted.
- `derived_report`: reports that can be regenerated. These need a small history window.
- `raw_import`: supplier, browser, API, or source files. Store one canonical copy with source-hash proof.
- `temp_debug`: helper files, retries, browser leftovers, and temporary traces. These need short time limits.
- `failed_partial`: incomplete run debris. Keep only when it is tied to an active failure investigation.

## Forbidden Patterns
- Do not create endless timestamped full-folder copies.
- Do not create repeated full SQLite backups unless a real write is about to happen.
- Do not keep raw browser/API dumps forever when a compact summary and canonical source pointer are enough.
- Do not add a one-off cleanup script into a daily loop unless it is promoted into registry-backed housekeeping.
- Do not delete anything from Google Sheets or align the local database to Sheets as part of housekeeping.

## Required Proof
- Run housekeeping in dry-run mode first.
- Confirm the manifest lists exact paths, sizes, rule names, and expected recovery.
- Run apply mode only at a safe flow boundary and only for registry-approved cleanup classes.
- Confirm `out/housekeeping/storage_health.latest.csv` has no FAIL for the affected flow.
