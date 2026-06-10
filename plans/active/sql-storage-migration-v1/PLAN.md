# Plan

## Goal
- Final outcome: SellerOne uses SQL as the long-term operational source of truth, with CSVs retained only for compatibility exports, publish snapshots, rollback bundles, and human-readable proof.

## Non-goals
- Do not remove all CSVs in one pass.
- Do not change Google Sheets.
- Do not rewrite business logic while migrating storage.
- Do not run any migration while live systems or API callers are active.
- Do not use downstream CSV exports to hide source-data problems.

## Current State
- A, B, E, H, O, and Feeder-related work all use CSV handoffs today.
- `project_control/DATA_BLUEPRINT_REGISTRY.csv` tracks 55 critical datasets across A, B, E, H, and System ownership.
- `project_control/ARCHITECTURE.md` already defines PostgreSQL as the intended production database.
- `scripts/core/out_paths.py` already shows a compatibility pattern for some live writer paths.
- H is live but still reliability-gated, so H storage cutover must happen late and only through controlled proof.

## Target State
- PostgreSQL is the production SQL authority.
- SQLite is allowed only for tests or local development.
- CSV exports remain available while scripts, Sheets publishing, proof bundles, and rollback still need them.
- Each dataset has one owner flow and one canonical SQL table or table family.
- Flow-owned proof gates decide when each flow can move from CSV to SQL.

## Mandatory Pause Policy
- Before backup, SQL seed, schema creation against production data, shadow replay, or cutover, pause all running systems and API callers.
- "All running systems and API callers" includes:
- A cycle
- B cycle and B supervisor
- E cycle
- H cycle, H scheduler ownership, H controlled run owner, and home-time monitor
- O cycle or operator UI jobs that write artifacts
- Feeder or supplier scanner jobs
- `run_api_collection.py`
- direct SP-API scripts
- LWA token refresh scripts started by local flows
- FX API refresh scripts
- controlled restart controller
- any background process writing `out/`, `data/`, or SQL migration tables
- The pause must be proven before work starts by checking processes, lock files, owner markers, and recent log movement.
- If a process cannot be paused cleanly, migration work parks before touching storage.

## Systems Touched
- Flow(s): A, B, E, H, O, Feeder, System
- Shared dependencies: `out/`, `data/`, `config/`, `reference/`, Google Sheets caches, SP-API outputs, FX cache, runtime locks, manifests
- Runtime or scheduler ownership concerns: B maintenance handoff, H scheduler pause/resume, controlled restart ownership, API collector ownership

## File And Output Ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Data blueprint registry | System | input | `project_control/DATA_BLUEPRINT_REGISTRY.csv` | Starting dataset contract map |
| Data lineage report | System | input | `project_control/DATA_LINEAGE_REPORT.md` | Starting read/write map |
| Architecture target | System | input | `project_control/ARCHITECTURE.md` | Names PostgreSQL target |
| Backup manifest | Migration | output | `out/backups/sql_storage_migration_v1/<timestamp>/manifest.csv` | Created before code changes |
| Backup summary | Migration | output | `out/backups/sql_storage_migration_v1/<timestamp>/summary.json` | Counts, hashes, runtime state |
| SQL schema migrations | Migration | output | `scripts/core/storage/migrations/` | Not created until Batch 002 |
| Storage adapter | Migration | output | `scripts/core/storage/` | Not created until Batch 002 |
| CSV compatibility exports | Flow owner | output | existing CSV paths | Kept during migration |

## Data Freshness And Health Checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| B core finance and token tables | flow-defined | flow-defined | B-scoped health | First major flow candidate after backup |
| A inventory and fees tables | flow-defined | flow-defined | A-scoped health | Requires owned A proof path |
| E analytics tables | flow-defined | flow-defined | E-scoped health | Migrate after A/B sources are stable |
| H repricing and market-intel tables | flow-defined | flow-defined | H-scoped health | Migrate late due to live repricing risk |
| System health and manifests | run-defined | run-defined | split health profiles | Do not make stale health look fresh |

## Integration Points
- APIs: SP-API, LWA token endpoint, FX APIs, any API collection script.
- Sheets: read/write behavior remains unchanged unless the user explicitly approves a sheet change.
- Local DB: new SQL store becomes shadow first, then primary by flow.
- CSV or file handoffs: remain during migration as exports and proof artifacts.

## Migration Phases
### Phase 0 - Full Pause And Backup
- Pause all running systems and API callers.
- Prove no active owners remain.
- Create full backup bundle and manifest.
- No SQL cutover work is allowed until this phase is complete.

### Phase 1 - Storage Map And Schema Design
- Use the registry and lineage report to group datasets by owner flow.
- Define SQL tables, keys, indexes, freshness fields, run metadata, and rollback export paths.
- Add health-check requirements before implementation.

### Phase 2 - SQL Shadow Mode
- Seed SQL from current CSVs.
- Keep CSV as runtime authority.
- Compare SQL against CSV row counts, keys, totals, and latest timestamps.
- Fix source ownership gaps before promoting any table.

### Phase 3 - B Flow SQL Primary With CSV Export
- Convert B-owned writers to write SQL first.
- Emit existing CSVs after successful SQL transaction.
- Run boundary-safe B proof only after B maintenance handoff and finalization.

### Phase 4 - A Flow SQL Primary With CSV Export
- Convert A-owned inventory, stock, fee, and health-source datasets.
- Use owned A proof path.
- Do not use standalone A015 as proof unless explicitly requested.

### Phase 5 - E Flow SQL Primary With CSV Export
- Convert E analytics outputs after B/A source data is stable.
- Run owned E cycle proof.

### Phase 6 - H Flow SQL Primary With CSV Export
- Convert H only after lower-risk flows are proven.
- Pause H scheduler ownership first.
- Run guarded controlled H proof.
- Resume scheduler ownership and prove owner restoration.

### Phase 7 - CSV Dependency Retirement
- Remove only proven obsolete CSV reads.
- Keep publish snapshots, last 3 rollback snapshots, proof bundles, and human review exports.

## Risks And Mitigations
- Risk: a live process writes CSV while migration is reading it.
- Mitigation: mandatory full pause, lock/process checks, and manifest timestamp checks.
- Risk: SQL import changes data types in ways that alter results.
- Mitigation: explicit schema checks, dtype preservation rules, and total reconciliation.
- Risk: one-off scripts bypass SQL and mutate old CSV truth.
- Mitigation: no daily import of one-off scripts, storage-mode guardrails, and compatibility export policy.
- Risk: H repricing becomes unstable during cutover.
- Mitigation: migrate H late, use controlled isolation, keep CSV fallback until live proof is confirmed.
- Risk: Sheets and local storage diverge.
- Mitigation: no Sheet changes without approval; local SQL migration starts from current local artifacts only.

## Proof Rules
- Code fix applied: storage code or adapters are merged into repo files with storage-mode flags and tests.
- Isolated verification passed: unit tests plus seed/export reconciliation pass on controlled fixtures and backup data.
- Live loop verification confirmed: flow-owned proof completes after finalization, scoped health is fresh, ownership is restored, and CSV compatibility exports match SQL.

## Batch List
- Batch 001: full pause checklist, backup manifest tool, backup runbook, and no-live-owner proof plan.
- Batch 002: storage adapter skeleton, schema migration framework, and fixture-level tests.
- Batch 003: CSV-to-SQL seed and SQL-to-CSV export utilities.
- Batch 004: SQL shadow reconciliation against backed-up data.
- Batch 005: B025 token COGS ledger SQL-primary pilot.
- Batch 006: B010 token operations SQL-primary expansion.
- Batch 007: B014 token daily checklist SQL-primary expansion.
- Batch 008: A006 stock events SQL-primary pilot.
- Batch 009: E001 sales velocity SQL-primary pilot.
- Batch 010: H004 market snapshot SQL-primary pilot.
- Batch 011: CSV dependency retirement and long-term retention policy.
- Batch 012: E002 ROI snapshot SQL-primary expansion.
- Batch 013: E003/E004/E005 analytics SQL-primary expansion.
- Batch 014: E006/E007 sales truth SQL-primary expansion.
- Batch 015: B012 token events SQL-primary expansion.
- Batch 016: B004 diagnostic outputs SQL-primary expansion.
- Batch 017: B004 order master SQL-primary expansion.
- Batch 018: B006 FX ledgers SQL-primary expansion.
- Batch 019: B008 refund token events SQL-primary expansion.
- Batch 020: B009 stock adjustment token events SQL-primary expansion.
- Batch 021: B003 financial events Level 3 official SQL-primary expansion.
- Batch 022: A004 fee outputs SQL-primary expansion.
- Batch 023: A005 inventory report outputs SQL-primary expansion.
- Batch 024: stock receipts latest SQL-primary expansion.
- Batch 025: inbound shipment contents SQL-primary expansion.
- Batch 026: Product DB preview SQL-primary expansion.
- Batch 027: B order archive SQL-primary expansion.
- Batch 028: token live files SQL-primary expansion.
- Batch 029: SQL-first reader migration for remaining registered dependencies.
- Batch 030: rollback export validation and re-enable proof planning.
- Batch 031: B-owned SQL-primary local proof without live APIs or Sheet writes.
- Batch 032: E-owned SQL-primary isolated proof without Sheet writes.
- Batch 033: H-owned controlled SQL-primary proof with scheduler paused and Sheet publish disabled.
- Batch 034: A-owned SQL-primary isolated proof with Sheet writers and token mutation steps disabled.
- Batch 035: live scheduler restoration for active non-reboot A/B/H tasks under SQL-primary defaults.
- Batch 036: F/O New Product Review SQL completion plan for review packs, review events, UI drafts, and dependency-map repair.
- Batch 037: O/F contract IO SQL expansion for schema-declared O/F process handoffs.
- Batch 038: B finance/order SQL expansion for Level 1/2/3 finance outputs, order snapshots, Order Master inputs, and orders-sheet source reads.

## Current Restoration State
- Active A/B/H batch entrypoints now default to `SELLERONE_STORAGE_MODE=sql_primary_csv_export` and `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`.
- Active non-reboot scheduler tasks restored: `AMZ Orders`, `AMZ H Cycle`, and `AMZ Pricing Summary`.
- B live restoration confirmed by finalized restored cycles `B_20260428T164227Z` and `B_20260428T165629Z`.
- H live restoration confirmed by finalized continuous production run `20260428T164339Z` and immediate next run `20260428T170156Z`.
- A scheduler restoration confirmed by enabled `AMZ Pricing Summary`; next scheduled run is `29/04/2026 06:00:00` local time.
- Intentionally still disabled: `AMZ Controlled Restart`, `AMZ Restart Postcheck`, and `AMZ Pricing Summary Hourly`.

## Known Remaining CSV Scope
- Batch 036 completed the registered F/O New Product Review SQL path.
- Batch 037 moved the wider O/F contract layer to SQL-aware contract IO and seeded existing O/F contract CSVs into SQL.
- Batch 038 moved the B finance/order CSV group to SQL-aware IO and seeded existing B finance/order CSVs into SQL.
- Refreshed dependency map on 2026-04-29 after Batch 038 shows:
  - `registered_dependency_count=508`
  - `sql_primary_pilot_proven_count=537`
  - `csv_dependency_remaining_count=0`
  - `unresolved_dynamic_count=710`
  - `unregistered_csv_count=606`
- Remaining registered CSV dependencies: none at the current P006 scan level.
- CSV files are still intentionally written as compatibility exports for rollback, operator download, and older tooling.
- Remaining unregistered CSV references are not approved as canonical storage; the largest remaining groups include token stock reconciliation, transaction ledgers, PnL daily, merchant listing snapshots, inbound delivery/status, fee VAT ledgers, and reference/config CSVs.

## Archive Rule
- This plan can move to archive only after every migrated flow has proof, rollback has been tested, and remaining CSV exports are documented as intentional.
