# SO21 Output Retention Rules

Created: 2026-06-08 23:14 UK
Job: SO21-OUTPUT-RETENTION-RULES
Mode: custodian planning and control only
Packet: sellerone_manager/tasks/approved/MGR_SO21_OUTPUT_RETENTION_RULES.md

## Plain-English Purpose

This file is the rule sheet for SellerOne output storage.

It does not clean anything. It works like labels on warehouse shelves:

- some shelves are live stock and must not be touched
- some shelves are proof and need a long memory
- some shelves are repeated reports that can later use a keep-latest rule
- some shelves are temporary scraps that may become safe expiry candidates after proof

These rules are not an apply manifest. They do not authorize deletion, movement, compression, purge, archive apply, runtime change, database write, Sheet write, or business action.

## Evidence Used

Read-only inputs:

- `sellerone_manager/CONTROL/STORAGE_POLICY.md`
- `sellerone_manager/CONTROL/SO21_DATA_LIFECYCLE_AND_DEDUP_PLAN.md`
- `sellerone_manager/CONTROL/SO21_DATA_FAMILY_INVENTORY.md`
- `sellerone_manager/CONTROL/SO21_OVERNIGHT_CONTROL_TEST_PLAN.md`
- `sellerone_manager/CONTROL/RUNTIME_SAFETY_RULES.md`
- `sellerone_manager/tasks/approved/MGR_SO21_OUTPUT_RETENTION_RULES.md`

No file contents, database rows, Google Sheets, Product DB, Amazon data, scheduler state, or runtime process state were inspected or changed for this rules file.

## Retention Classes

| Class | Plain-English meaning | Default retention rule | Cleanup approval level |
|---|---|---|---|
| `manual_protected` | Control files, task packets, configs, code, and other human-governed files | Keep. Never auto-delete. | Approval-required, usually excluded |
| `current_runtime` | Files that live scripts, active owners, locks, or current proof may need | Keep while active. Never clean by age alone. | Approval-required and owner-proof-required |
| `state_rolling` | Current snapshots where a small history is useful | Keep latest plus a fixed rolling history after owner proof. | Approval-required before first apply |
| `rollback` | Backups and recovery folders | Keep newest recovery sets and named critical rollback sets. Older sets require recovery proof before action. | Approval-required |
| `audit_history` | MOT, proof, manifest, governance, and decision evidence | Keep or archive under policy. Do not silently delete. | Approval-required |
| `raw_import` | Supplier, browser, API, email, or source data | Keep canonical source proof. Dedupe only after source pointer and owner proof exist. | Approval-required before first apply |
| `derived_report` | Reports that can be rebuilt from source evidence | Candidate for keep-latest, keep-last-N, or keep-last-N-days. | Automatic-safe only after dry-run proof and protected exclusions |
| `temp_debug` | Debug traces, retry folders, browser scraps, and test leftovers | Candidate for short expiry after investigation closes. | Automatic-safe only after investigation-close proof |
| `failed_partial` | Incomplete output from failed runs | Keep while tied to active investigation, then expire by rule. | Approval-required before first apply |

## Protected Exclusions

These are excluded from automatic cleanup. A future manifest must still exclude them unless a separate approved packet and explicit protected approval say otherwise.

| Path or family | Why it is protected | Rule |
|---|---|---|
| `sellerone_manager/CONTROL/` | SellerOne control memory and governance | Never auto-delete, move, compress, purge, or archive-apply |
| `sellerone_manager/tasks/` | Canonical queue packets | Never auto-delete or queue-move from retention cleanup |
| root `AGENTS.md` and `sellerone_manager/AGENTS.md` | Operating instructions | Never auto-delete |
| `config/`, `secrets/`, `.git/` | Configuration, secrets-adjacent state, and source history | Never auto-delete |
| `out/sql/sellerone_dev.sqlite3` and current DB files | Local database truth and runtime state | Manual protected |
| `out/locks/` | Live ownership signals | Protected unless a separate stale-lock packet proves action |
| `out/systems/*/live/` | Flow-owned live runtime output | Protected until each flow owner defines current/live semantics |
| `out/systems/M/mot/` | MOT proof and control evidence | Keep as audit history |
| `out/manifests/` current/proof manifests | Flow proof and cleanup proof | Keep current and proof-critical manifests |
| root `out/*.csv`, `out/*.json`, `out/*.log` modified on active runtime dates | Mixed live outputs | Do not clean as a bundle |
| Google Sheets, Product DB, local DB alignment targets, Amazon/security paths | Protected business systems | Not in scope for Custodian cleanup |

## Automatic-Safe Candidates

These are candidates for future automation only after a dry-run manifest proves exact paths, classes, sizes, rules, protected exclusions, and recovery route. They are not approved for cleanup now.

| Family | Measured reason | Proposed future rule | Required proof before automatic apply |
|---|---|---|---|
| `out/housekeeping/housekeeping_report.*.csv` | Repeated large reports, about 40-46 MB each | Keep latest 7 daily reports, keep one monthly audit snapshot, expire older duplicate-style reports | Prove reports are rebuildable or have selected audit copies |
| `out/housekeeping/storage_housekeeping_report.*.csv` | Repeated storage inventory reports, about 40-44 MB each | Pair with housekeeping report rule: keep latest 7 daily reports plus monthly snapshots | Prove no report is named as active proof for an open packet |
| `out/reports/` derived reports | 466 files, 15.75 MB, mostly rebuildable reporting | Keep latest 30 days unless a report is named proof | Prove source evidence exists and no active packet references the report |
| Low-risk `temp_debug` folders after investigation closes | Temporary/debug class has short business value after closure | Keep 14 days after close marker, then include in dry-run expiry manifest | Prove investigation is closed and owner confirms no active use |
| Rebuildable duplicate derived reports by hash | Data lifecycle plan identifies dedupe as a goal | Keep newest copy and named proof copy; mark older duplicates as candidates | Prove duplicate by hash and preserve one recovery route |

Automatic-safe means "safe to propose and dry-run automatically." It does not mean delete automatically today.

## Approval-Required Candidates

These families may offer large storage benefit, but they can affect proof, rollback, or runtime. They need owner proof, an approved dry-run manifest, and explicit approval before any apply.

| Family | Measured reason | Proposed future rule | Why approval is required |
|---|---|---|---|
| `out/systems/H/staged/` | 3,810 files, 126.29 GB, largest measured opportunity | Keep current staged run, latest N successful staged runs, and named proof snapshots; expire failed/old staged runs only after owner proof | H staged data may be current proof or pricing/intelligence evidence |
| `out/systems/H/live/` | 155,947 files, 4.93 GB | Keep as current runtime; no cleanup until H defines safe live compaction or ownership rule | Live runtime output |
| `out/systems/F/price_list_manager/` | 28,835 files, 2.24 GB | Split into current input, processed history, raw source proof, and rebuildable reports before any rule | F scanner/product review may need current evidence |
| `out/systems/F/history/` | 55 files, 2.30 GB | Keep while F proof remains relevant; archive or thin only after F owner confirms proof value | Could be rollback or audit history |
| `out/systems/F/inbox/` | 129 files, 0.21 GB | Keep until processed-state rule exists | Inbox may contain unprocessed source data |
| `out/backups/` | 10,922 files, 9.48 GB | Keep newest approved rollback sets plus named critical migrations; older sets only after recovery route is proven | Backups are rollback material |
| `out/sql_migration/` | 585 files, 795.56 MB | Keep until DB migration recovery policy retires them | Migration proof and rollback value |
| `out/manifests/B/` | 25,386 files, 217.26 MB | Keep current and proof-critical manifests; thin old non-proof manifests only by flow rule | B affects finance/orders/tokens truth |
| `out/manifests/H/` | 10,829 files, 14.09 MB | Keep current and proof-critical manifests; bounded history after H owner proof | H proof and runtime evidence |
| `out/snapshots/H/` | 10,291 files, 376.24 MB | Keep latest plus rolling history after H owner identifies current/proof snapshots | H state snapshots may explain current behavior |
| `out/proof/` | 863 files, 111.01 MB | Keep or archive by proof policy; do not delete by age alone | Audit history |
| `out/analysis_reports/` | 1,708 files, 780.76 MB | Keep last 30 to 90 days or named proof reports after source proof is confirmed | May contain investigation proof |
| Root `out/` mixed files | Mixed live and old outputs | Classify per owner and file family before any rule | Folder-level cleanup could hit live files |
| `out/locks/` | 8,438 files, 21.92 MB | Separate stale-lock review packet only | Lock files can represent active ownership |

## Family Rules

### H System Outputs

Current rule:

- Protect `out/systems/H/live/`.
- Treat `out/systems/H/staged/` as approval-required.
- Do not clean H by extension, age, or size alone.

Future rule direction:

- define current staged run
- define completed successful staged runs
- define failed partial staged runs
- keep latest N successful staged runs plus named proof snapshots
- expire old failed partial runs only after investigation-close proof

Expected benefit:

- H staged was measured at 126.29 GB, so this is the largest likely storage improvement.
- The business benefit is lower disk pressure, faster scans, faster backups, and less confusion between live H truth and repeated staged copies.

### F System Outputs

Current rule:

- Protect `out/systems/F/live/` and `out/systems/F/inbox/`.
- Treat `out/systems/F/price_list_manager/` and `out/systems/F/history/` as approval-required.
- Do not expire F061 or scanner evidence without an F owner rule.

Future rule direction:

- split current input from processed history
- keep canonical raw source proof
- dedupe duplicate derived price-list reports after hash proof
- expire small temp/debug folders only after related investigation closes

Expected benefit:

- F has high file count, especially 28,835 files in `price_list_manager`.
- The main benefit is faster folder scans and clearer scanner evidence, not just disk reduction.

### B System Outputs

Current rule:

- Protect B outputs and B manifests.
- Do not clean B data without B owner proof.

Reason:

- B can affect finance, orders, tokens, and business truth. The safe default is keep.

### A, E, O, M, And Shared System Outputs

Current rule:

- Protect A source-fact outputs.
- Protect M/MOT control proof.
- Protect shared runtime outputs until consumers are mapped.
- Keep E and O until owner rules exist because their measured storage pressure is low.

Future rule direction:

- define small bounded history rules after each owner confirms which outputs are current and which are rebuildable.

### Backups And Rollback

Current rule:

- Keep backups.
- Do not remove or compress rollback sets from this packet.

Future rule direction:

- keep newest approved rollback sets
- keep named migration and major repair rollback sets until recovery route is retired
- require a dry-run manifest before any archive, compression, or deletion proposal

Expected benefit:

- `out/backups/` measured 9.48 GB. A keep-count policy can reduce repeated rollback bulk while preserving recovery.

### Housekeeping And Storage Reports

Current rule:

- Keep for now.
- This is the strongest automatic-safe candidate family after dry-run proof.

Future rule direction:

- keep latest 7 daily reports
- keep one monthly audit snapshot
- keep reports named by open packets
- classify older repeated reports as dry-run expiry candidates

Expected benefit:

- Reduces repeated large control reports and makes future inventory scans lighter.

### Manifests

Current rule:

- Keep current and proof-critical manifests.
- Treat B and H manifests as approval-required.

Future rule direction:

- per-flow manifest history rule
- keep active manifests and proof manifests
- thin old non-proof manifests only after owner proof

### Snapshots

Current rule:

- Keep H snapshots until H owner defines current/proof semantics.

Future rule direction:

- keep latest snapshot plus rolling history
- keep named proof snapshots
- expire older rebuildable snapshots only by manifest

## Bugs And Risks Found

| Risk | Plain-English explanation | Safe response |
|---|---|---|
| H staged output is very large and recent | It may be repeated staging output, but it may also be current proof | Create a separate H staged retention packet before any action |
| Backups look reducible but are rollback paths | Removing the wrong backup can remove the fastest recovery route | Require recovery route proof and approval |
| Root `out/` mixes live and old files | A folder-level cleanup could touch live runtime files | Classify by owner and family first |
| Locks may be stale or active | A lock can be a traffic cone for a running process | Use a stale-lock packet, not retention cleanup |
| Derived reports may be referenced as proof | A report that looks rebuildable may still be named evidence | Exclude open-packet proof and named proof files |

## Efficiency Improvements

| Improvement | Expected business benefit | Needed before action |
|---|---|---|
| H staged rolling rule | Largest likely disk reduction and faster storage scans | H owner proof and dry-run manifest |
| Housekeeping report retention | Less repeated reporting bulk and faster control scans | Prove selected reports are audit snapshots and others are rebuildable |
| Backup keep-count policy | Lower rollback storage while preserving recovery | Recovery route and approval |
| F price-list manager classification | Lower file-count drag and clearer scanner evidence | F owner map |
| Manifest history rule | Fewer tiny files while keeping proof | Per-flow proof-manifest rules |

## Graph Recommendations

Use measured data from `SO21_DATA_FAMILY_INVENTORY.md` for morning reporting.

| Graph | X axis | Y axis | Why it helps |
|---|---|---|---|
| Storage by top-level family | `out/` family | GB | Shows `out/systems/` dominates storage |
| Systems storage by flow | A/B/E/F/H/M/O/shared | GB and file count | Shows H is the first practical target |
| H staged run size over time | staged timestamp | MB per run | Shows whether staged files are repeated or growing |
| Extension storage mix | extension | GB | Shows CSV files drive the storage load |
| Backup sets by age and size | backup folder timestamp | GB | Supports a rollback keep-count decision |
| Housekeeping reports over time | report timestamp | MB | Shows repeated control-report cost |

## Future Cleanup Gate

No cleanup can occur from this file alone.

Before any apply action, SellerOne must have:

1. Approved packet for the exact family.
2. Owner proof for current/live/proof semantics.
3. Dry-run manifest listing exact path, class, size, proposed action, rule, and recovery route.
4. Protected exclusion check.
5. Safe boundary check for live owners and locks.
6. Explicit approval if deletion, movement, compression, purge, archive apply, database change, Sheet write, scheduler change, runtime change, or business action is involved.
7. Post-apply proof, if apply is ever approved in a future packet.

## Blockers And Gaps

No Windows permission, locked-file, Task Scheduler access, credential, app connector, machine-level, or protected-boundary blocker was hit while creating these rules.

Known evidence gaps:

- Duplicate content is not proved by this rules file.
- H staged completion state is not proved.
- F price-list manager current/input/history ownership is not mapped.
- Backup recovery priority is not ranked.
- No cleanup manifest exists for these rules, by design.

## Read-Only Proof

Actions performed:

- read the worker, queue, runtime, role, blocker, overnight, lifecycle, storage policy, data inventory, and packet instructions
- wrote this retention-rules control file
- separated automatic-safe candidates from approval-required candidates
- preserved protected exclusions

Actions not performed:

- no cleanup apply
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
- no queue widening
- no code change

## Recommended Next Operational Step

continue with SO21-DATA-CLEANUP-AUTOMATION-DESIGN after reviewer confirms these rules are not an apply manifest
