# Project Brief

## Ticket
- Ticket name: SQL Storage Migration v1
- Date opened: 2026-04-28
- Owner: Codex

## Business Problem
- SellerOne currently uses many CSV files across `out/`, `data/`, `config/`, and `reference/`.
- CSVs are easy to inspect, but they become risky when multiple scripts read and write related files at different times.
- The highest risks are stale files, duplicate truth layers, partial writes, and unclear ownership between A, B, E, H, O, one-off scripts, and API collectors.

## Goal
- Move SellerOne toward SQL as the system-wide operational storage layer.
- Keep CSVs only as compatibility exports, publish snapshots, rollback evidence, and human-readable proof bundles.
- Complete the migration without changing Google Sheets unless explicitly asked.

## Why Now
- The repo already names PostgreSQL as the target production storage model.
- A, B, E, H, O, Feeder, and future operations-loop work will be easier and safer if they use one durable storage layer instead of many CSV handoffs.
- This must happen before the system grows too much more around CSV-only contracts.

## Constraints
- All running systems and API callers must be paused before migration work touches live storage.
- No overlapping A, B, E, H, O, Feeder, API collector, home-time monitor, scheduler, or controlled-restart owner may run during backup, SQL seeding, or cutover steps.
- No Google Sheets changes unless the user explicitly approves that exact action.
- No local DB changes to "match" Sheets, or Sheets changes to "match" local DB, without approval.
- One-off scripts must not be imported by daily loops.
- Root cause and ownership must be fixed upstream, not masked by downstream output adjustment.

## Definition Of Success
- A complete backup bundle exists before storage code changes.
- A backup manifest records file counts, sizes, hashes, row counts, and current runtime ownership state.
- SQL schema exists for the first approved dataset group.
- CSV-to-SQL seed and SQL-to-CSV export paths exist.
- Shadow reconciliation proves row counts, key counts, important totals, and freshness fields match before SQL becomes primary.
- Each flow is migrated only after its own isolated tests and flow-owned proof pass.
- Rollback can switch a flow back to CSV mode without touching Sheets.

## Reference Material
- `project_control/ARCHITECTURE.md`
- `project_control/DATA_BLUEPRINT.md`
- `project_control/DATA_BLUEPRINT_REGISTRY.csv`
- `project_control/DATA_LINEAGE_REPORT.md`
- `project_control/FORCED_PROOF_WINDOWS.md`
- `plans/templates/CODING_PLAN_TEMPLATE.md`
