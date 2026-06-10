# SO21 Data Family Inventory

Created: 2026-06-08 22:43 UK
Job: SO21-DATA-FAMILY-INVENTORY
Mode: read-only custodian inventory
Packet: sellerone_manager/tasks/approved/MGR_SO21_DATA_FAMILY_INVENTORY.md

## Plain-English Summary

This report is a map of the data warehouse. It names the main output families, who likely owns them, what class they belong to, and what direction a future retention rule should take.

No cleanup was applied. No file was deleted, moved, renamed, compressed, purged, archived, or changed.

## Measurement Scope

Root inspected:

- `out/`

Evidence used:

- file path
- file name
- file size
- extension
- modified time
- folder grouping

Not inspected or changed:

- file contents
- database rows
- Google Sheets
- Product DB
- Amazon
- Task Scheduler
- runtime processes

## Protected Current Runtime Exclusions

These areas must remain excluded from cleanup unless a separate approved packet, proof window, manifest, and Luke-approved protected action allow otherwise.

| Path or family | Likely owner | Class | Retention direction |
|---|---|---|---|
| `out/sql/sellerone_dev.sqlite3` | shared runtime / local DB | current_runtime | Manual protected. Do not delete, move, compress, purge, or align from this packet. |
| `out/locks/` | live flow ownership | current_runtime | Manual protected while locks may represent active owners. Stale-lock review needs a separate approved packet. |
| `out/systems/*/live/` | A/B/E/F/H/O/M flows | current_runtime | Keep current live outputs. Future cleanup must first identify each flow's current/live pointer. |
| `out/systems/M/mot/` and other MOT/control proof | Manager / MOT | audit_history | Keep as proof history unless a separate archive policy explicitly classifies older evidence. |
| `out/manifests/` | A/B/E/H/O flows | audit_history / current_runtime | Keep current manifests and proof manifests. Future rule can keep bounded history only after owner proof. |
| root `out/*.csv`, `out/*.json`, `out/*.log` with modified time on 2026-06-08 | live A/B/E/H/F outputs | current_runtime | Treat as active until each flow owner confirms latest/current semantics. |
| `sellerone_manager/CONTROL/` | control system | manual_protected | No cleanup. This inventory is the only file written here by this worker. |
| `sellerone_manager/tasks/` | queue | manual_protected | No queue movement or cleanup from this packet. |

## Top-Level Measured Families

| Family | Files | Size | Newest observed | Likely owner | Class | Proposed retention direction |
|---|---:|---:|---|---|---|---|
| `out/systems/` | 192,153 | 140.87 GB | 2026-06-08 | flow-owned runtime | mixed current_runtime / audit_history / failed_partial / derived_report | Split by flow and subfolder before any cleanup. Protect live areas. |
| `out/backups/` | 10,922 | 9.48 GB | 2026-06-05 | repair/build workers | rollback | Keep latest approved rollback sets by rule; older backup sets need manifest review before any action. |
| `out/housekeeping/` | 1,787 | 1.85 GB | 2026-06-08 | Custodian / storage reporting | derived_report / audit_history | Repeated large storage reports are a strong retention-rule candidate. No deletion now. |
| `out/sql/` | 1 | 1.18 GB | 2026-06-08 | local DB runtime | current_runtime | Fully protected. |
| `out/sql_migration/` | 585 | 795.56 MB | 2026-05-02 | DB migration proof | rollback / audit_history | Keep until DB migration proof policy decides archive window. |
| `out/analysis_reports/` | 1,708 | 780.76 MB | 2026-06-08 | reporting / analysis | derived_report | Candidate for keep-latest or keep-last-N-days after source proof is confirmed. |
| `out/snapshots/` | 10,293 | 376.31 MB | 2026-06-08 | mostly H snapshots | state_rolling / audit_history | Candidate for rolling history rule, but current flow snapshots must be protected until owner confirms. |
| `out/manifests/` | 36,610 | 233.97 MB | 2026-06-08 | flow manifests | audit_history / current_runtime | Keep current and proof-critical manifests. Future rule can thin old non-proof manifests only by dry-run manifest. |
| root `out/` large live files | many individual files | several hundred MB plus | 2026-06-08 | mostly H/B/API/finance/token flows | current_runtime / derived_report | Do not clean as a bundle. Needs per-flow retention naming. |
| `out/proof/` | 863 | 111.01 MB | 2026-05-21 | proof workers | audit_history | Keep or archive. Do not delete without proof-retention policy. |
| `out/reports/` | 466 | 15.75 MB | 2026-06-08 | reporting | derived_report | Candidate for keep-latest or keep-last-N-days. |
| `out/locks/` | 8,438 | 21.92 MB | 2026-06-08 | runtime locks | current_runtime | Protected. Stale-lock candidates need a separate review packet. |

## Flow-Owned Systems Breakdown

| Family | Files | Size | Newest observed | Likely owner | Class | Proposed retention direction |
|---|---:|---:|---|---|---|---|
| `out/systems/H/` | 159,759 | 131.22 GB | 2026-06-08 | H pricing / seller intelligence | mixed current_runtime / state_rolling / derived_report | Highest measured opportunity. Must split `live` from `staged` before any cleanup. |
| `out/systems/F/` | 29,794 | 5.15 GB | 2026-06-08 | F scanner / product review | mixed current_runtime / raw_import / audit_history / temp_debug | Protect `live` and current inbox. History and temp need retention rules. |
| `out/systems/B/` | 245 | 0.34 GB | 2026-06-08 | B finance/orders/tokens | current_runtime / audit_history | Protect. B data can affect business truth. |
| `out/systems/O/` | 1,821 | 0.28 GB | 2026-06-06 | O review/product flow | derived_report / audit_history | Candidate for bounded history after O owner proof. |
| `out/systems/shared/` | 240 | 0.04 GB | 2026-06-08 | shared runtime | current_runtime | Protect until all consumers are mapped. |
| `out/systems/M/` | 264 | 0.01 GB | 2026-06-08 | manager/MOT/control | audit_history / current_runtime | Protect as control evidence. |
| `out/systems/A/` | 10 | small | 2026-06-08 | A source-fact refresh | current_runtime / audit_history | Protect. A is source facts. |
| `out/systems/E/` | 3 | small | 2026-06-08 | E study/reporting | derived_report / audit_history | Low storage pressure. Keep until E retention rule exists. |

## H Family Detail

Measured H subfolders:

| Family | Files | Size | Newest observed | Class | Retention direction |
|---|---:|---:|---|---|---|
| `out/systems/H/staged/` | 3,810 | 126.29 GB | 2026-06-08 | failed_partial / state_rolling / derived_report candidate | Biggest storage opportunity. Future rule should identify safe completed staged runs, keep current proof, and retain a bounded rolling set. No action now. |
| `out/systems/H/live/` | 155,947 | 4.93 GB | 2026-06-08 | current_runtime | Protected current runtime. Do not clean from this packet. |
| `out/systems/H/todo/` | 1 | small | 2026-02-18 | current_runtime / workflow marker | Protect until H owner confirms unused. |
| `out/systems/H/archive/` | 1 | small | 2026-03-03 | audit_history | Archive policy needed before action. |

Observed large H repeated file pattern:

- repeated `out/systems/H/staged/<timestamp>/data/offer_snapshot_facts.csv`
- many are about 350 MB each on 2026-06-08
- this looks like repeated staged data, not a single live file

Retention direction:

- define "current H staged run" and "completed H staged proof" first
- keep current live data protected
- consider future rolling staged rule such as keep latest N successful staged runs plus proof snapshots, only after H owner proof and dry-run manifest

Expected business benefit if handled later:

- lower disk pressure
- faster backup and storage scans
- less confusion between current H truth and repeated staged copies
- cleaner morning evidence for pricing/intelligence health

## F Family Detail

Measured F subfolders:

| Family | Files | Size | Newest observed | Class | Retention direction |
|---|---:|---:|---|---|---|
| `out/systems/F/history/` | 55 | 2.30 GB | 2026-05-01 | audit_history / rollback | Candidate for archive rule after proof value is confirmed. |
| `out/systems/F/price_list_manager/` | 28,835 | 2.24 GB | 2026-06-08 | raw_import / derived_report / current_runtime | Needs owner mapping before cleanup. High file count makes it a future dedupe candidate. |
| `out/systems/F/live/` | 576 | 0.39 GB | 2026-06-08 | current_runtime | Protected. |
| `out/systems/F/inbox/` | 129 | 0.21 GB | 2026-06-08 | raw_import / current_runtime | Protect current inbox until processed-state rule exists. |
| `out/systems/F/temp/` | 52 | small | 2026-04-13 | temp_debug | Future short-expiry candidate after proof. |
| `out/systems/F/diagnostics/` | 53 | small | 2026-05-12 | audit_history / temp_debug | Keep while related investigation is active; otherwise candidate for retention rule. |
| `out/systems/F/page_evidence_backfill/` | 77 | small | 2026-05-21 | audit_history / raw_import | Keep until F061 evidence policy confirms expiry. |

## Backup Family Detail

Largest measured backup groups:

| Family | Files | Size | Newest observed | Class | Retention direction |
|---|---:|---:|---|---|---|
| `out/backups/sql_storage_migration_v1/` | 69 | 1.40 GB | 2026-04-29 | rollback / audit_history | Keep until SQL migration recovery path is formally retired. |
| `out/backups/f_phase10_split_proof_before_20260522T115737Z/` | 2,926 | 1.30 GB | 2026-05-22 | rollback | Candidate for keep-count rule after F proof closes. |
| `out/backups/f_phase13_split_enforced_proof_before_20260522T125800Z/` | 3,042 | 1.30 GB | 2026-05-22 | rollback | Candidate for keep-count rule after F proof closes. |
| `out/backups/f_phase16_split50_runtime_before_20260522T141642Z/` | 451 | 1.28 GB | 2026-05-22 | rollback | Candidate for keep-count rule after F proof closes. |
| `out/backups/f_phase15_split25_before_20260522T135942Z/` | 433 | 1.28 GB | 2026-05-22 | rollback | Candidate for keep-count rule after F proof closes. |
| `out/backups/f_storage_drift_reconcile_20260605T085236Z/` | 8 | 1.27 GB | 2026-06-05 | rollback | Recent rollback. Keep for now. |
| `out/backups/f_phase8_sql_to_csv_active_run_20260522T103127Z/` | 9 | 1.17 GB | 2026-05-22 | rollback | Candidate only after recovery route is confirmed. |

Plain-English finding:

- The backup family is not random trash. It is rollback material. It may still be reducible, but only after a keep-count policy and recovery route are approved.

## Housekeeping Family Detail

Largest root-level housekeeping files observed:

| Pattern | Example size | Modified dates | Class | Retention direction |
|---|---:|---|---|---|
| `housekeeping_report.<timestamp>.csv` | about 40-46 MB each | repeated April to June 2026 | derived_report / audit_history | Strong candidate for keep-latest plus monthly archive rule. |
| `storage_housekeeping_report.<timestamp>.csv` | about 40-44 MB each | repeated May to June 2026 | derived_report / audit_history | Strong candidate for dedupe or paired-report rule. |

Plain-English finding:

- Housekeeping reports are useful, but many large copies appear to repeat the same kind of inventory. Future cleanup should first decide which reports are proof and which are rebuildable.

## Manifest Family Detail

| Family | Files | Size | Newest observed | Class | Retention direction |
|---|---:|---:|---|---|---|
| `out/manifests/B/` | 25,386 | 217.26 MB | 2026-06-08 | current_runtime / audit_history | Protect current B manifests. Future rule can reduce old non-proof manifests only after B owner proof. |
| `out/manifests/H/` | 10,829 | 14.09 MB | 2026-06-08 | current_runtime / audit_history | Protect current H manifests. |
| `out/manifests/A/` | 233 | 1.91 MB | 2026-06-08 | audit_history | Low pressure; keep for now. |
| `out/manifests/E/` | 158 | 0.66 MB | 2026-06-08 | audit_history | Low pressure; keep for now. |
| `out/manifests/O/` | 5 | 0.05 MB | 2026-04-04 | audit_history | Low pressure; keep for now. |

## Snapshot Family Detail

| Family | Files | Size | Newest observed | Class | Retention direction |
|---|---:|---:|---|---|---|
| `out/snapshots/H/` | 10,291 | 376.24 MB | 2026-06-08 | state_rolling / audit_history | Candidate for rolling retention after H owner confirms current and proof snapshots. |
| `out/snapshots/pipeline_stabilization_20260311T164403Z/` | 2 | 0.07 MB | 2026-03-11 | audit_history | Keep or archive. Low pressure. |

## Extension-Level Evidence

Top storage by extension:

| Extension | Files | Size |
|---|---:|---:|
| `.csv` | 33,454 | 140.58 GB |
| `.sqlite3` | 10 | 8.38 GB |
| `.log` | 68,022 | 4.73 GB |
| `.json` | 129,349 | 1.22 GB |
| `.before_b_finance_seed` | 1 | 1.12 GB |
| `.1` | 10 | 208.17 MB |
| `.before_contract_seed` | 1 | 92.42 MB |
| `.png` | 1,106 | 60.86 MB |
| `.jsonl` | 21 | 52.19 MB |
| no extension | 452 | 35.87 MB |

Plain-English finding:

- CSV files are the main storage driver. The first future graph should show CSV growth by owner family, not just total disk usage.

## Risks

| Risk | Why it matters | Safest response |
|---|---|---|
| H staged data is very large and recent | It may be repeated completed staging output, but it may also contain current proof. | Do not touch now. Create a follow-up H staged retention packet with owner proof. |
| SQL backups are large | They are rollback paths. Removing the wrong one could remove the quickest recovery route. | Keep until a rollback keep-count rule is approved. |
| Root `out/` mixes live and old files | A simple folder cleanup could hit current runtime files. | Future cleanup must classify by file family and flow owner, not by folder only. |
| Locks are numerous | Some may be stale, but some may protect live ownership. | Separate stale-lock review packet. |
| Housekeeping reports duplicate inventory style | Repeated reports consume space and may slow future scans. | Future retention rule can keep latest plus selected audit snapshots. |

## Efficiency Opportunities

These are opportunities only. They are not cleanup instructions to perform now.

| Opportunity | Measured reason | Expected benefit | Required next proof |
|---|---|---|---|
| H staged rolling rule | `out/systems/H/staged/` measured 126.29 GB | Largest likely storage reduction and faster scans | H owner must define current staged run, proof runs, and safe expiry rule. |
| Backup keep-count policy | `out/backups/` measured 9.48 GB, with several 1.17-1.40 GB groups | Reduce repeated rollback bulk while preserving recovery | Approved rollback policy plus dry-run manifest. |
| Housekeeping report retention | repeated 40-46 MB report pairs | Smaller control-report storage and faster inventory scans | Decide which housekeeping reports are audit proof vs rebuildable. |
| F price-list manager review | 28,835 files and 2.24 GB | Reduce file-count overhead and possible duplicates | F owner map of live/current/input/history. |
| Manifest history rule | 36,610 manifest files | Lower file count while preserving proof | Per-flow proof manifest retention rule. |

## Graph Recommendations For Morning Reporting

These are recommended charts only, based on measured metadata.

| Graph | X axis | Y axis | Why it helps |
|---|---|---|---|
| Storage by top-level family | folder family | GB | Shows that `out/systems` dominates storage. |
| `out/systems` by flow | A/B/E/F/H/M/O/shared | GB and file count | Shows H as the first practical target. |
| H staged run size over time | staged timestamp | MB per run | Shows whether H staged files are growing steadily or repeating fixed-size copies. |
| Extension storage mix | extension | GB | Shows CSV as the main storage driver. |
| Backup sets by age and size | backup folder timestamp | GB | Helps choose a rollback keep-count rule without guessing. |
| Housekeeping reports over time | report timestamp | MB | Shows repeated control-report cost. |

## Blockers And Gaps

No Windows permission, locked-file, credential, connector, machine-level, or protected-boundary blocker was hit during this inventory.

Known evidence gaps:

- This report did not inspect file contents, so duplicate content is not proved here.
- This report did not determine whether each H staged run is complete, failed, or still needed.
- This report did not determine exact retention windows. It only proposes directions.
- This report did not update queue status.

## Read-Only Proof

Actions performed:

- read control instructions and approved packet
- measured `out/` using metadata only
- grouped data families by path, owner, class, and likely retention direction
- wrote this inventory under `sellerone_manager/CONTROL/`

Actions not performed:

- no deletion
- no file movement
- no rename
- no compression
- no purge
- no archive apply
- no database write
- no Sheet write
- no Product DB or local DB alignment
- no runtime change
- no Task Scheduler change
- no Amazon or security action
- no business action
- no cleanup apply

## Recommended Next Operational Step

continue with SO21-OUTPUT-RETENTION-RULES using this inventory as the factual input
