# SO21 Data Cleanup Automation Design

Created: 2026-06-09 00:43 UK
Job: SO21-DATA-CLEANUP-AUTOMATION-DESIGN
Mode: custodian planning and control only
Packet: sellerone_manager/tasks/approved/MGR_SO21_DATA_CLEANUP_AUTOMATION_DESIGN.md

## Plain-English Purpose

This file designs the future cleanup automation for SellerOne storage.

It does not build the automation and it does not approve cleanup.

Think of the automation like a warehouse clerk who first walks the aisles with a clipboard:

- measure what exists
- label what kind of data it is
- point out likely duplicates
- draft a dry-run manifest
- stop before touching anything protected
- ask for approval before any file-changing cleanup

The first version must be read-only by default. It can recommend cleanup candidates, but it must not delete, move, rename, compress, purge, archive-apply, mutate runtime, write databases, write Sheets, change schedulers, or touch business systems.

## Evidence Used

Read-only inputs:

- `sellerone_manager/CONTROL/STORAGE_POLICY.md`
- `sellerone_manager/CONTROL/RUNTIME_SAFETY_RULES.md`
- `sellerone_manager/CONTROL/QUEUE_CONTRACT.md`
- `sellerone_manager/CONTROL/OPERATIONS_BLOCKER_PROTOCOL.md`
- `sellerone_manager/CONTROL/SO21_OVERNIGHT_CONTROL_TEST_PLAN.md`
- `sellerone_manager/CONTROL/SO21_DATA_LIFECYCLE_AND_DEDUP_PLAN.md`
- `sellerone_manager/CONTROL/SO21_DATA_FAMILY_INVENTORY.md`
- `sellerone_manager/CONTROL/SO21_OUTPUT_RETENTION_RULES.md`
- `sellerone_manager/CONTROL/SO21_DUPLICATE_DATA_REPORT.md`
- `sellerone_manager/tasks/approved/MGR_SO21_DATA_CLEANUP_AUTOMATION_DESIGN.md`

Measured evidence carried forward:

- `out/systems/` is the largest top-level family at 140.87 GB.
- `out/systems/H/staged/` is the largest measured opportunity at 126.29 GB.
- `out/backups/` is 9.48 GB and is rollback material, not trash.
- `out/sql/sellerone_dev.sqlite3` is protected current runtime data.
- duplicate reporting found 75.63 MB of hash-proven sampled duplicate space and 17.82 GB of same-name, same-size likely duplicate space.
- H staged and rollback/database copies are the biggest future opportunities, but both need owner proof before any apply.

No file contents, database rows, Google Sheets, Product DB, Amazon data, scheduler state, runtime process state, or business queues were inspected or changed for this design.

## Automation Layers

The design must be layered so each stage is safer than the next. The early stages are like drawing a map before lifting boxes.

| Layer | Name | Allowed to run automatically | What it does | What it must not do |
|---|---|---|---|---|
| 1 | Storage report | Yes, read-only | Counts files, sizes, modified dates, extensions, and family totals | No file changes |
| 2 | Duplicate report | Yes, read-only with bounded limits | Finds exact duplicate samples by hash and likely duplicates by metadata | No dedupe apply and no deletion |
| 3 | Protected exclusion check | Yes, read-only | Marks protected paths and refuses risky families | No override of protected data |
| 4 | Dry-run cleanup manifest | Yes, preview-only | Writes proposed candidate rows with path, class, size, rule, action, and recovery route | No apply action |
| 5 | Manager review packet | Yes, as a report recommendation only | Recommends exact follow-up packets and approval needs | No queue widening without Rep approval |
| 6 | Apply gate | No automatic apply | Checks whether a future approved apply packet exists | Must stop unless exact approval exists |
| 7 | Cleanup apply | No | Future-only, separate approved packet, separate proof window | Not approved by this design |

## Allowed Automatic Work

These actions can be automatic because they only observe and report.

| Automation | Output | Safe reason | Required limits |
|---|---|---|---|
| Top-level storage report | `out/housekeeping/storage_report.<timestamp>.csv` or equivalent future controlled path | Metadata-only measurement | Must exclude file contents and protected credentials |
| Family storage index | `out/housekeeping/storage_family_index.<timestamp>.csv` | Shows owner families and growth | Must label unknown families as `needs_owner_mapping` |
| Duplicate candidate report | `out/housekeeping/duplicate_candidates.<timestamp>.csv` | Reports candidates without changing data | Large hashing must be bounded or separately approved |
| Protected exclusion report | `out/housekeeping/protected_exclusions.<timestamp>.csv` | Confirms no-touch paths before any manifest | Must fail closed if a path cannot be classified |
| Dry-run cleanup manifest | `out/housekeeping/cleanup_manifest_dry_run.<timestamp>.csv` | Preview only, like a shopping list before purchase | Every row must include action, rule, class, proof, and recovery route |
| Graph data extracts | `out/housekeeping/storage_graph_data.<timestamp>.csv` | Helps Luke see where storage pressure is coming from | Must use measured data only |

Automatic here means "can run without changing files." It does not mean "can clean files."

## Approval-Required Work

These actions require a separate approved packet and explicit approval before they can happen.

| Action | Approval reason |
|---|---|
| Delete files | Permanent output loss risk |
| Move files | Runtime and proof path risk |
| Rename files | Runtime and proof path risk |
| Compress files | Recovery and path mutation risk |
| Purge files | Permanent output loss risk |
| Archive apply | File movement or compression risk |
| Deduplicate by replacing files | Runtime and proof path risk |
| Change local DB or Product DB facts | Protected business data |
| Write Google Sheets | Protected business data |
| Change scheduler state | Runtime ownership risk |
| Change worker/runtime state | Runtime ownership risk |
| Touch Amazon/security paths | Protected security boundary |
| Change queue scope | Rep/queue ownership boundary |

## Protected Data Exclusions

The automation must exclude these by default. If any future manifest includes one of these, the manifest must fail and report a blocker.

| Path or family | Protection reason | Default automation behavior |
|---|---|---|
| `sellerone_manager/CONTROL/` | Control memory and governance | Exclude from cleanup apply |
| `sellerone_manager/tasks/` | Canonical queue packets | Exclude from cleanup apply |
| root `AGENTS.md` and `sellerone_manager/AGENTS.md` | Operating instructions | Exclude from cleanup apply |
| `.git/` | Source history | Exclude from cleanup apply |
| `config/` and `secrets/` | Configuration and secrets-adjacent state | Exclude from cleanup apply |
| `out/sql/` current DB files | Local database truth | Exclude unless separate DB recovery packet approves |
| `out/sql/sellerone_dev.sqlite3` | Current runtime DB | Always protected |
| `out/locks/` | Live ownership markers | Exclude unless separate stale-lock packet approves |
| `out/systems/*/live/` | Flow-owned live runtime output | Exclude until owner semantics are proved |
| `out/systems/F/live/` and F browser profiles | Scanner-owned runtime and F061 security-sensitive path | Exclude |
| `out/systems/M/mot/` | MOT and control proof | Exclude from cleanup apply |
| `out/manifests/` current/proof manifests | Flow proof and cleanup proof | Exclude unless owner proof narrows exact old non-proof rows |
| `out/backups/` | Rollback material | Approval-required only |
| `out/sql_migration/` | Migration proof and rollback | Approval-required only |
| `out/proof/` | Audit evidence | Approval-required only |
| Google Sheets, Product DB, Amazon/security paths | Protected business systems | Out of scope |

## Stop Conditions

Automation must stop and write a blocker record if any of these happen.

| Stop condition | Plain-English meaning | Safest response |
|---|---|---|
| A protected path appears in an apply candidate row | The checklist accidentally points at a no-touch shelf | Fail the manifest and report the path |
| Owner cannot be identified | The data shelf has no responsible flow | Mark `needs_owner_mapping` and do not propose apply |
| File classification is unknown | The automation cannot tell whether it is live, proof, backup, or rebuildable | Exclude from apply candidates |
| File access fails | Windows, lock, or permission issue blocks inspection | Record blocker with path and error summary |
| Runtime owner or lock may be active | A live process may depend on the data | Stop before apply and require owner proof |
| Large hashing would exceed the proof window | Duplicate proof could run too long | Use bounded scan and recommend a separate packet |
| Any mutation would be required | The next step would change files or business state | Stop and require approval |
| Evidence contradicts retention rules | The map and rule sheet disagree | Open reconciliation ticket before cleanup |
| It is after the approved proof window | Work could be interrupted by restart or runtime boundary | Stop and write a post-window check requirement |

Blocker records must include:

- affected job
- what was attempted
- what failed
- evidence or error summary
- safest proposed fix
- whether Luke approval is needed

## Dry-Run Manifest Contract

A dry-run manifest is a preview checklist. It is not an apply command.

Every candidate row must include:

- `manifest_id`
- `created_utc`
- `job_ref`
- `path`
- `family`
- `owner`
- `class`
- `size_bytes`
- `modified_utc`
- `candidate_reason`
- `proposed_action`
- `retention_rule`
- `proof_required`
- `recovery_route`
- `protected_exclusion_checked`
- `apply_approval_required`
- `status`

Allowed `status` values:

- `report_only`
- `candidate_needs_owner_proof`
- `candidate_needs_approval`
- `excluded_protected`
- `blocked_needs_investigation`

Forbidden `status` values for this design:

- `approved_to_delete`
- `approved_to_move`
- `approved_to_compress`
- `approved_to_purge`
- `applied`

## Candidate Families

These are future candidates only. This design does not authorize cleanup.

| Family | Evidence | Future automation behavior | Gate before apply |
|---|---|---|---|
| `out/housekeeping/` repeated reports | 1.85 GB and repeated 40-46 MB report style | Report keep-latest and monthly snapshot candidates | Prove no report is named proof |
| `out/reports/` derived reports | 466 files, 15.75 MB | Report last-30-days retention candidates | Prove source evidence exists |
| old `temp_debug` folders | Retention rules identify as short-expiry candidates | Report candidates after investigation close marker | Owner confirms investigation closed |
| `out/systems/H/staged/` | 126.29 GB, about 9.16 GB likely duplicate space | Report by staged run, size, file pattern, and age | H owner defines current staged run and proof runs |
| `out/backups/` | 9.48 GB rollback material | Report keep-count candidates only | Recovery route and explicit approval |
| `out/sql_migration/` | 795.56 MB migration proof | Report archive/keep candidates only | Migration rollback retirement proof |
| `out/systems/F/price_list_manager/` | 28,835 files, 2.24 GB | Report current/input/history split candidates | F owner map |
| `out/manifests/B/` and `out/manifests/H/` | 36,610 manifest files total | Report old non-proof manifest candidates | Per-flow proof-manifest rule |
| `out/snapshots/H/` | 10,291 files, 376.24 MB | Report rolling-history candidates | H owner confirms current/proof snapshots |

## Safe Apply Gate Design

If cleanup apply is ever built later, it must be a separate command or packet from reporting.

The apply gate must refuse to run unless all checks are true:

1. Exact approved apply packet exists for the specific family.
2. Dry-run manifest exists and is newer than the rule change.
3. Manifest has no protected exclusions in candidate rows.
4. Owner proof exists for current/live/proof semantics.
5. Recovery route is named and tested where rollback matters.
6. Runtime owner and lock check is clear.
7. Explicit approval exists for deletion, movement, compression, purge, archive apply, database write, Sheet write, scheduler change, runtime change, Amazon/security action, or business action.
8. Post-apply proof path is named before apply starts.

If any check is false, apply must stop before changing files.

## Graph Recommendations

Use measured data only. Do not invent graph values.

| Graph | Data source | X axis | Y axis | Business benefit |
|---|---|---|---|---|
| Storage by top-level family | inventory | family | GB | Shows where disk pressure lives |
| Systems storage by flow | inventory | A/B/E/F/H/M/O/shared | GB and file count | Shows H as first practical target |
| H staged run size over time | future dry-run manifest | staged timestamp | MB per run | Shows repeated staging bulk |
| Likely duplicate space by family | duplicate report | family | GB | Separates major opportunities from noise |
| Exact vs likely duplicates | duplicate report | proof type | MB or GB | Keeps proved duplicates separate from suspicion |
| Backup sets by age and size | inventory and dry-run manifest | backup timestamp | GB | Helps choose rollback keep-count safely |
| Housekeeping reports over time | inventory and dry-run manifest | report timestamp | MB | Shows repeated control-report cost |

## Bugs And Risks Found

| Risk | Plain-English explanation | Safe response |
|---|---|---|
| H staged is huge and recent | The biggest storage shelf may still contain current proof | Report and dry-run only until H owner proof exists |
| Database copies look duplicate | Matching DB files may be rollback protection | Exclude current DB and require recovery proof for backups |
| Backups are not trash | Repeated rollback files can be intentional | Keep until keep-count policy and approval |
| F live/cache duplicates exist | Some duplicate-looking files sit in scanner-owned live profiles | Exclude F live and security-sensitive profile paths |
| Same-name and same-size is not content proof | Matching labels do not prove matching contents | Hash before any future dedupe apply |
| Root `out/` is mixed | Live files and old files sit near each other | Classify by owner and family, not just folder age |
| Housekeeping reports can grow from reporting itself | The measuring tool can create its own clutter | Add retention for housekeeping reports before frequent scheduling |

## Efficiency Improvements

| Improvement | Expected business benefit | Required proof before action |
|---|---|---|
| H staged dry-run manifest | Biggest likely disk pressure reduction and faster scans | H owner proof |
| Housekeeping report retention | Stops the reporting layer from becoming another storage problem | Named proof exclusion check |
| Rollback keep-count report | Reduces backup clutter later while preserving recovery | Tested recovery route and approval |
| F price-list manager classification | Faster scanner evidence searches and less file-count drag | F owner map |
| Manifest history rule | Fewer tiny files while keeping proof | Per-flow proof-manifest rule |

## Recommended Automation Schedule

This is a design recommendation only. It does not create, enable, disable, or mutate any automation.

| Report | Suggested cadence | Reason |
|---|---|---|
| Storage report | Daily during active cleanup planning, then weekly | Tracks growth without touching files |
| Duplicate candidate report | Weekly or on demand | More expensive than size counting |
| Dry-run cleanup manifest | On demand per approved family packet | Must stay tied to review and approval |
| Graph data extract | Morning reporting only when needed | Helps Luke see trends without raw logs |

Do not schedule these until a separate approved automation-creation packet exists.

## Recovery And Rollback Path

This design created a new control document only.

Current rollback path:

- remove `sellerone_manager/CONTROL/SO21_DATA_CLEANUP_AUTOMATION_DESIGN.md` if the manager rejects the design
- no runtime file, output data, database, Sheet, scheduler, automation, Amazon/security path, or business state needs rollback because none was changed

For future cleanup apply, rollback must be stronger:

- named recovery route before apply
- protected exclusion proof
- pre-apply manifest snapshot
- post-apply storage proof
- owner signoff when runtime/proof data is involved

## Blockers And Gaps

No Windows permission, locked-file, Task Scheduler access, credential, app connector, machine-level, or protected-boundary blocker was hit while creating this design.

Known evidence gaps:

- H staged current/successful/failed state is not proved.
- F price-list manager current/input/history ownership is not mapped.
- Backup recovery priority is not ranked.
- Large H staged files and DB/rollback files were not fully hashed.
- No cleanup apply manifest exists for these rules, by design.
- No automation was built, scheduled, enabled, disabled, or changed.

## Acceptance Proof

This design satisfies the packet acceptance proof because:

- the automation design exists under `sellerone_manager/CONTROL/`
- it starts with read-only reporting and dry-run manifests
- it does not approve blind cleanup
- it names stop conditions and protected data exclusions
- it does not build or enable cleanup automation that changes files

## Read-Only Proof

Actions performed:

- read the worker, queue, runtime, role, blocker, overnight, lifecycle, inventory, duplicate, retention, storage-policy, and packet instructions
- wrote this design-only control file
- separated automatic read-only reports from approval-required apply actions
- named protected exclusions and stop conditions
- preserved a simple rollback path for this new planning file

Actions not performed:

- no automatic deletion
- no cleanup apply
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
- no automation creation, enabling, disabling, or mutation
- no queue widening
- no code change

## Recommended Next Operational Step

continue with SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN after reviewer confirms this file is design-only and not an apply manifest
