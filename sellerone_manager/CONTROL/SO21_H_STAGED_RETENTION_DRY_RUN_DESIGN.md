# SO21 H Staged Retention Dry-Run Design

Created: 2026-06-09
Job: SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN
Role: Custodian Worker
Mode: design-only and read-only evidence review
Packet: `tasks/approved/MGR_SO21_H_STAGED_RETENTION_DRY_RUN_DESIGN.md`

## Plain-English Summary

This report designs the safe future route for reviewing `out/systems/H/staged`.

Think of H staged like a warehouse shelf full of repeated working boxes. Some boxes may be old copies, but some may be the current proof, rollback material, or failure evidence. This report labels what a future dry-run should check before anyone is allowed to move, delete, compress, purge, archive, or dedupe anything.

No cleanup was applied by this worker.

## Evidence Used

Read-only inputs:

- `AGENTS.md`
- `WORKER_CHAT.md`
- `CONTROL/ROLE_BOOTSTRAP.md`
- `CONTROL/QUEUE_CONTRACT.md`
- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`
- `CONTROL/SO21_MORNING_IMPROVEMENT_REPORT_20260609.md`
- `CONTROL/SO21_DATA_FAMILY_INVENTORY.md`
- `CONTROL/SO21_DUPLICATE_DATA_REPORT.md`
- `CONTROL/SO21_OUTPUT_RETENTION_RULES.md`
- `CONTROL/SO21_DATA_CLEANUP_AUTOMATION_DESIGN.md`
- `tasks/approved/MGR_SO21_H_STAGED_RETENTION_DRY_RUN_DESIGN.md`
- read-only metadata from `../out/systems/H/staged`
- read-only tail of `../out/systems/H/live/H_cleanup_ledger.jsonl`
- read-only H MOT evidence from `../out/systems/M/hourly_mot_H.csv`
- read-only H manifest evidence from `../out/manifests/H/`
- read-only registry evidence from `../project_control/log_housekeeping_registry.json`

Evidence inspected:

- path names
- file names
- file sizes
- extensions
- folder timestamps
- H cleanup ledger lines
- H MOT rows
- H registry rules
- selected manifest header fields

Evidence not inspected or changed:

- file contents inside H staged CSVs
- database rows
- Google Sheets
- Product DB
- Amazon or security paths
- Task Scheduler
- runtime process state
- business queues

## Fresh H Staged Measurement

Observed path from the SellerOne root:

- `out/systems/H/staged`

Fresh metadata measured on 2026-06-09:

| Measure | Observed value |
|---|---:|
| Staged run folders | 241 |
| Files | 3,816 |
| Total size | 127.15 GB |
| CSV files | 3,575 |
| JSON files | 241 |
| Oldest file timestamp observed | 2026-02-13 11:00:35 local |
| Newest file timestamp observed | 2026-06-09 12:23:03 local |

Largest repeated file families:

| File name | Count | Total size | Meaning |
|---|---:|---:|---|
| `offer_snapshot_facts.csv` | 241 | 81.91 GB | Largest repeated staged output |
| `execution_log.csv` | 241 | 23.24 GB | Large repeated run evidence |
| `decision_log.csv` | 241 | 8.36 GB | Large repeated decision evidence |
| `sku_ceiling_events.csv` | 241 | 8.05 GB | Large repeated safety/ceiling evidence |
| `scenario_rollup.csv` | 241 | 2.67 GB | Repeated rollup output |
| `probe_windows.csv` | 241 | 2.47 GB | Repeated probe evidence |

Plain-English reading:

- H staged is still the biggest practical storage shelf to understand.
- The data is run-shaped: many timestamp folders with similar files.
- The safest future manifest should be run-level first, then file-level inside each run.
- A simple rule like "delete old CSVs" would be unsafe because the CSVs include proof and decision evidence.

## Existing H Cleanup Evidence

Existing H cleanup ledger evidence was found at:

- `out/systems/H/live/H_cleanup_ledger.jsonl`

Recent ledger lines show an existing H runtime cleanup policy named `h_staged_retention` with:

- target: `out/systems/H/staged`
- action recorded: `deleted`
- reason: `age_ttl_days=7;count_cap=240`
- repeated one-folder removals on 2026-06-09

Registry evidence from `project_control/log_housekeeping_registry.json` also names:

- rule id: `h_staged_publish_snapshots`
- path glob: `out/systems/H/staged/*`
- storage class: `rollback`
- retention: newest 5 complete snapshots
- action on expiry: `delete`
- blockers: `h_run_unfinalized`, `block_if_state_unknown`

Important gap:

- The H cleanup ledger currently shows a count cap of 240.
- The central registry says the staged publish snapshot rule should keep the newest 5 complete snapshots.
- H MOT also reported this cap mismatch as a warning.

Safe interpretation:

- The future dry-run design must not copy either rule blindly.
- Owner proof must reconcile the live cleanup behavior, the central registry rule, and the current H proof state before any future manifest proposes an apply action.

## Current H Health Context

Read-only H MOT evidence from 2026-06-09 11:00 UTC showed:

| Check | Status | Design meaning |
|---|---|---|
| `h_latest_manifest_state` | fail | Latest H manifest at that time showed a failed run |
| `h_terminal_publish_truth` | fail | Terminal and publish markers did not agree at that point |
| `h_boundary_finalizer_truth` | fail | Boundary/finalizer proof was not clean |
| `h_reliability_window` | fail | Recent H run window was not clean enough |
| `h_storage_cleanup_safety` | warn | Staged folder count and registry cap disagreed |
| `h_lock_and_heartbeat_state` | ok | H ownership evidence existed at that time |

Later read-only terminal marker evidence showed run `20260609T110424Z` finalized and published ok, but this report does not declare H healthy. A future manifest must use a fresh H owner proof taken at manifest time.

Plain-English reading:

- H staged cleanup must treat failed, warning, and successful runs differently.
- If H is not at a clean boundary, staged cleanup should stop before proposing apply.
- A completed publish marker alone is not enough; the manifest must tie the staged folder, manifest, terminal marker, publish marker, and current/live pointer together.

## Required Categories

A future H staged dry-run manifest should classify each staged run folder into one of these categories.

| Category | Plain-English meaning | Default action |
|---|---|---|
| `protected_current` | The staged run matches the current H run, latest publish run, active terminal marker, active lock, or active manifest path | Exclude |
| `protected_named_proof` | The staged run is named by an open ticket, MOT evidence, manifest proof, failure investigation, or Luke decision | Exclude |
| `successful_publish_rollback` | The run completed and published successfully and is kept as rollback material | Candidate only after keep-count rule is reconciled |
| `failed_partial_active_investigation` | The run failed or ended ambiguously and may explain a current H failure | Exclude until investigation closes |
| `failed_partial_closed` | The run failed, but a later proof supersedes it and owner confirms it is no longer needed | Candidate needs owner proof and approval |
| `duplicate_candidate` | Same-name, same-size, or hash-proven repeated files exist, but the run is not yet cleared for apply | Candidate needs owner proof, hash proof if dedupe is proposed, and approval |
| `audit_history` | Older run evidence with proof value | Keep or archive only under proof-retention policy |
| `blocked_needs_owner_mapping` | The dry-run cannot tell whether the run is current, proof, rollback, failed, or rebuildable | Exclude and report blocker |

## Owner-Proof Checks

Before any cleanup manifest can propose deletion, movement, compression, purge, archive apply, or dedupe, H owner proof must answer these questions.

| Proof check | Evidence source | Pass condition |
|---|---|---|
| Current H run identity | `H_cycle_current_run_id.txt`, lock evidence, latest manifest, terminal marker | One current or clean no-owner boundary is visible |
| Latest publish identity | `H_cycle_last_publish_info.txt`, publish run id marker | Latest publish run is readable and status is ok, or the reason for no publish is clear |
| Latest terminal identity | `H_cycle_last_terminal_info.txt` | Terminal run, state, and stage are readable |
| Staged folder mapping | staged folder timestamp and H manifest run id | Each candidate folder maps to a known run or is marked unknown |
| Manifest final state | `out/manifests/H/<date>/H_<run>.json` | Run is successful, failed, warning, or unknown with no guessing |
| Reliability window | H MOT or equivalent fresh proof | Recent window is clean enough, or failed runs are excluded |
| Active lock and heartbeat | H lock/heartbeat evidence | No candidate belongs to an active owner |
| Open-ticket proof exclusion | current tickets, H packets, MOT rows | No candidate is named by active proof or investigation |
| Registry reconciliation | cleanup ledger and `log_housekeeping_registry.json` | Count cap and keep rule agree before any apply proposal |
| Recovery route | newest protected staged runs plus manifests | Rollback path is named before any apply |

If any check fails, the manifest row must be `blocked_needs_owner_mapping`, `excluded_protected`, or `candidate_needs_owner_proof`. It must not be marked apply-ready.

## Future Dry-Run Manifest Fields

A future dry-run manifest should be a preview checklist, not an apply command.

Required fields:

- `manifest_id`
- `created_utc`
- `job_ref`
- `root_path`
- `run_folder`
- `run_id`
- `folder_modified_utc`
- `folder_file_count`
- `folder_size_bytes`
- `largest_file_name`
- `largest_file_size_bytes`
- `category`
- `owner`
- `manifest_path`
- `manifest_final_state`
- `terminal_state`
- `publish_status`
- `active_lock_checked`
- `open_ticket_checked`
- `registry_rule_id`
- `registry_rule_version`
- `ledger_policy_seen`
- `candidate_reason`
- `duplicate_evidence_type`
- `hash_proof_required`
- `proposed_action`
- `retention_rule`
- `proof_required`
- `recovery_route`
- `protected_exclusion_checked`
- `apply_approval_required`
- `status`
- `blocker_reason`
- `reviewer_notes`

Allowed `status` values:

- `report_only`
- `excluded_protected`
- `candidate_needs_owner_proof`
- `candidate_needs_approval`
- `blocked_needs_owner_mapping`
- `blocked_policy_conflict`

Forbidden `status` values:

- `approved_to_delete`
- `approved_to_move`
- `approved_to_compress`
- `approved_to_purge`
- `approved_to_archive`
- `approved_to_dedupe`
- `applied`

## Protected Exclusions

These must be excluded from any automatic apply route by default.

| Path or family | Why excluded |
|---|---|
| `sellerone_manager/CONTROL/` | Control memory and governance |
| `sellerone_manager/tasks/` | Canonical queue packets |
| `out/systems/H/live/` | H current runtime and proof markers |
| `out/systems/H/live/H_cleanup_ledger.jsonl` | Audit evidence for cleanup activity |
| `out/systems/H/staged/<current run>` | Current or possibly current staged data |
| `out/systems/H/staged/<latest published run>` | Fast rollback and publish proof |
| `out/systems/H/staged/<failed or ambiguous active investigation run>` | Failure evidence |
| `out/manifests/H/` current and proof manifests | H run proof and boundary evidence |
| `out/systems/M/mot/` and `out/systems/M/hourly_mot_H.csv` | Manager/MOT proof |
| `out/locks/` and H lock files | Runtime ownership signals |
| `out/sql/` and current DB files | Local database truth |
| `out/backups/` and `out/sql_migration/` | Rollback and migration recovery |
| Google Sheets, Product DB, Amazon/security paths | Protected business systems |

## Future Dry-Run Route

The future route should work like a careful stocktake.

1. Read H owner proof first.
2. Read latest H manifest, terminal marker, publish marker, lock/heartbeat, and H MOT storage warning.
3. List staged run folders by metadata only.
4. Attach each staged folder to a run id and manifest where possible.
5. Classify each folder into the required categories.
6. Apply protected exclusions before candidate logic.
7. Reconcile the current cleanup ledger rule against the central registry rule.
8. Mark any unresolved conflict as `blocked_policy_conflict`.
9. Calculate run-level size and largest repeated file families.
10. Write a dry-run manifest with no apply status.
11. Write graph data from the manifest.
12. Stop for owner review and approval before any file-changing action.

## Graph Recommendations

Use measured data only. Do not invent missing values.

| Graph | Data source | X axis | Y axis | Why it helps Luke |
|---|---|---|---|---|
| H staged run size over time | future dry-run manifest | staged run timestamp | MB per run | Shows whether staged runs are steady repeated copies or growing |
| H staged category split | future dry-run manifest | category | GB and run count | Separates protected proof from possible candidates |
| H staged largest file families | current metadata or future manifest | file name | GB | Shows which files drive storage pressure |
| H staged current/proof/candidate stack | future manifest | category | GB | Makes the no-touch boundary visible |
| H staged policy conflict view | ledger and registry | rule source | keep count, TTL, status | Shows whether live cleanup and central registry agree |
| H run outcome versus staged size | manifests and staged metadata | manifest final state | GB and run count | Shows whether failed runs are a major storage driver |
| H staged duplicate candidates | duplicate report plus manifest | file name | likely duplicate GB | Keeps likely duplicates separate from apply approval |

## Blockers And Gaps

| Gap | What it means | Safest next step |
|---|---|---|
| H cleanup ledger and registry disagree | Ledger says count cap 240, registry says newest five complete snapshots | Reconcile in an H owner-proof packet before any apply manifest |
| H MOT showed recent H failures | Failed or ambiguous runs may be needed as evidence | Exclude failed/ambiguous runs until H owner closes the investigation |
| Existing H cleanup activity is outside this design | Ledger records deletes by the live H cleanup policy, not by this worker | Treat ledger as evidence; do not alter it here |
| Large H staged CSVs were not content-hashed | Same file names and sizes are not full duplicate proof | Hash only inside a bounded future dry-run packet if dedupe is proposed |
| Broad listing of `out/systems/H/live` timed out once | H live is large enough that broad scans are noisy | Use targeted owner-proof marker reads instead of broad live-folder scans |
| Completion state for every staged run is not mapped here | This report is design-only | Future manifest must map each run to manifests and markers |

No Windows permission, credential, connector, Task Scheduler access, protected-decision, or machine-level blocker stopped this report. The only evidence limit was one broad read-only H live listing that timed out; the safer replacement was targeted reads of named H proof files.

## Acceptance Proof

This report satisfies the packet because:

- it exists under `CONTROL/`
- it is design-only
- it separates protected/current data from candidate categories
- it requires H owner proof before any cleanup manifest
- it defines future dry-run manifest fields
- it names protected exclusions
- it recommends proposal graphs using measured data
- it records blockers and gaps
- it does not authorize cleanup apply

## Read-Only Proof

Actions performed by this worker:

- read the required role, queue, runtime, control, storage, duplicate, retention, automation-design, morning-report, and packet files
- inspected H staged metadata only
- inspected selected H cleanup ledger, MOT, registry, and manifest evidence read-only
- wrote this new design report under `CONTROL/`

Actions not performed by this worker:

- no deletion
- no movement
- no rename
- no compression
- no purge
- no archive apply
- no dedupe apply
- no H runtime run
- no H worker restart
- no Task Scheduler change
- no process kill
- no price change
- no Google Sheets write
- no database write or alignment
- no Product DB write
- no Amazon or security action
- no purchase, receiving, or send-to-Amazon action
- no business action
- no output mutation

## Rollback Path

This task created one new control report:

- `sellerone_manager/CONTROL/SO21_H_STAGED_RETENTION_DRY_RUN_DESIGN.md`

If the manager rejects this design, the rollback path is to remove this new report file only. No runtime output, staged data, database, Sheet, scheduler, Amazon/security path, queue packet, or business state was changed by this worker.

## Recommended Next Operational Step

continue with reviewer inspection of `CONTROL/SO21_H_STAGED_RETENTION_DRY_RUN_DESIGN.md` as a design-only report before any H staged manifest work is proposed
