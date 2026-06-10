# SellerOne 2.1 Operations Report

Generated: 2026-06-08

## Plain-English Status

Operations is now a back-office report, not a person Luke needs to talk to.

Its job is to collect the noisy facts - MOT, automations, storage, tokens, locks, schedulers, and repeated failures - and feed clear summaries into the Rep and the queue.

## Current Operations State

- SellerOne 2.1 phase: control desk stabilisation
- Luke approved unattended control-desk monitoring while away on 2026-06-08.
- Approved unattended scope: cleanup review, control-file readiness, queue visibility, and maintenance-mode planning preparation.
- Luke approved expanded tonight authority for safe control-desk work on 2026-06-08.
- Expanded tonight authority: Operations may create clean Worker and Reviewer threads as needed, move approved control tickets through status steps when evidence supports it, approve or register read-only control-desk automations inside the blueprint, archive old control clutter only when backed up first, prepare and review maintenance-mode design documents, and create follow-up tickets for blockers it finds.
- Luke approved controlled pause/restart authority for maintenance mode on 2026-06-08.
- Controlled pause/restart scope: Operations may design and later use a maintenance-record-based pause/restart model for named maintenance work. This must use a maintenance request, named target, explicit restart method, and post-restart health proof.
- Not approved unattended scope: blind process killing, permanent Task Scheduler changes, permanent deletion, Amazon login/security, price changes, Google Sheets writes, database alignment, purchase/receiving/send-to-Amazon, or queue edits outside approved task status updates.
- No-idle rule: if approved control-desk work exists, Operations must keep it moving, assign/review it, or record a real blocker. SellerOne should not sit with approved tasks available and no management action happening.
- Blocker logging rule: if Operations hits Windows permissions, locked files, Task Scheduler access limits, missing credentials, app connector limits, or any other machine-level restriction, it must record the blocker clearly with the affected job, what was attempted, what failed, and the safest proposed fix. It must not guess or silently skip the issue.
- Overnight test rule: overnight quiet-hours tests may run only as read-only or planning/control checks. They must not leave work half-finished across the expected 02:00 UK PC restart on 2026-06-09. Anything still active by 01:45 UK should be parked or recorded with a clear restart/check-after-reboot note.
- Automations found: 20
- Active automations: 1
- Paused automations: 19
- Queue contract: created
- Current state generator: created
- Current tickets generator: created
- Backlog generator: created
- AI usage report: created
- Legacy coding plan archive: complete
- Prompt and plan folder archive: complete
- Role file trim: complete
- Skill specs: complete
- `out/` subtree index: complete
- Custodian dry-run manifest: complete
- Dead automation and scheduler review: complete
- Windows scheduler pause decision: complete
- Automation rebuild plan: complete
- Paused Rep briefing pilot created: yes
- Rep briefing pilot activated: yes
- Active approved pilot automations: 1
- Custodian policy: created
- Instruction cleanup: initial bootstrap rewrite complete
- Cleanup performed in this task: no
- Runtime changes performed in this task: no

## AI Usage Snapshot

Observed after `SO21-STORAGE-INDEX-OUT-SUBTREE`.

- Actual AI billing/cost data connected: no
- Recommended next task from report: `SO21-AUTOMATION-ACTIVATION-DECISION`

The usage report is a pressure gauge, not a billing statement. Live coding-plan pressure, old prompt-folder pressure, repeated role-file detail, repeat workflow recipes, mixed `out/` storage classification, and the preview-only cleanup manifest are now handled. The dead automation and scheduler review is also complete. The Windows scheduler pause is complete for the approved eight tasks. The automation rebuild plan now exists; the next step is the first pilot activation decision.

## Out Subtree Snapshot

Observed during `SO21-STORAGE-INDEX-OUT-SUBTREE`.

| Class | Subtrees | Size MB | Custodian View |
|---|---:|---:|---|
| `current_runtime` | 4 | 141828.086 | protected live/runtime/proof areas |
| `rollback` | 3 | 9485.891 | backup history, manifest only |
| `audit_history` | 17 | 4175.370 | proof/report/history, archive by manifest only |
| `mixed_current_and_history` | 1 | 1080.718 | top-level `out/` files, manifest grouping needed |
| `temp_debug` | 24 | 0.319 | candidate only after dry-run and active-owner check |

The largest area is `out/systems` at 140629.435 MB. That is classified as `current_runtime` and must not be treated as cleanup material.

## Dry-Run Cleanup Manifest Snapshot

Observed during `SO21-CUSTODIAN-DRY-RUN-MANIFEST`.

- Manifest rows: 49
- Rows needing future approval before any apply: 45
- Protected exclusions: 5
- Preview candidate size: 4175.689 MB
- Protected size: 142908.804 MB
- Cleanup performed: no
- Recommended next task: `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`

Action counts:

- `exclude_keep`: 4
- `manifest_grouping_required`: 1
- `manifest_keep_count_review`: 3
- `preview_archive_candidate`: 17
- `preview_purge_candidate`: 24

The manifest explicitly keeps current runtime areas protected, including `out/systems`, `out/sql`, `out/locks`, and `out/parking`. The mixed top-level `out/_root_files` row also stays protected until it is split into exact files or groups.

## Automation And Scheduler Snapshot

Observed during `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`.

- Codex app automations found: 20
- Active Codex app automations: 1
- Paused Codex app automations: 19
- Windows scheduled tasks found: 11
- Ready Windows scheduled tasks: 0
- Scheduler pause decision required: no
- Recommended next task: `SO21-REP-BRIEFING-FIRST-RUN-PROOF`

Plain-English meaning:

Pausing Codex app automations did not pause every background scheduler. Luke approved a temporary Windows scheduler pause, and the eight approved scheduled tasks are now disabled. The pause did not delete, restart, or edit scheduler definitions.

Paused Windows scheduler rows:

- `AMZ Controlled Restart`
- `AMZ H Cycle`
- `AMZ Morning MOT Post A`
- `AMZ Morning MOT Post Restart`
- `AMZ Orders`
- `AMZ Price List Manager`
- `AMZ Pricing Summary`
- `SellerOne Manager Hourly MOT`

## Automation Rebuild Snapshot

Observed during `SO21-AUTOMATION-REBUILD`.

- Automations activated: 1
- Candidate automations to create paused: 3
- Paused pilot automations already created: 0
- Active approved pilot automations: 1
- Candidate automations deferred: 1
- Old SellerOne automations marked retire/do-not-resume: 5
- Old active SellerOne Codex automations: 0
- Windows scheduled tasks still ready after pause: 0
- Recommended next task: `SO21-REP-BRIEFING-FIRST-RUN-PROOF`

Plain-English meaning:

SellerOne now has a smaller proposed automation set instead of the old manager pulse pile. The first pilot, `SO21-REP-BRIEFING`, is active under the approved Rep briefing boundary. The remaining proof is its first scheduled read-only briefing run.

## Storage Lesson

The 2026-05-25 emergency cleanup estimated 667.123 GB of removable buildup.

That was the strongest evidence that SellerOne needed a Custodian lifecycle, not another one-off cleanup.

## Current Top-Level Storage Snapshot

Observed during `SO21-CUSTODIAN-POLICY`.

| Area | Size | Files | Custodian View |
|---|---:|---:|---|
| `data` | 798.9 MB | 93 | protected business facts |
| `project_control` | 484.8 MB | 281 | governance and proof history |
| `scripts` | 117.6 MB | 13280 | code protected |
| `plans` | 33.6 MB | 571 | historical/control context |
| `reference` | 33.1 MB | 66 | protected reference material |
| `tests` | 16.4 MB | 930 | code protected |
| `sellerone_manager` | 15.7 MB | 410 | control desk |
| `backups` | 7.0 MB | 12 | rollback protected |
| `config` | 0.2 MB | 99 | configuration protected |
| `docs` | 0.1 MB | 11 | documentation |
| `out` | 156570.758 MB measured by subtree index | 253625 | classified by subtree; cleanup manifest is preview-only |

## Important `out/` Observation

The `out/` folder is too mixed to treat as one cleanup target.

It contains live runtime files, locks, SQL files, flow evidence, backups, reports, tests, temp folders, and proof history. That is why SellerOne classified `out/` by subtree before producing the dry-run cleanup manifest.

That classification and dry-run manifest now exist. Any future cleanup still needs a fresh exact apply manifest, live-owner checks, and explicit approval before files are moved or removed.

## No-Touch Boundaries

Operations and Custodian must not change:

- worker runtime
- prices
- queues
- Google Sheets
- Product DB or local DB facts
- live SQL databases
- active lock files
- active scheduler ownership
- Amazon login/security state
- current task packets

## Recommended Operations Tickets

- `SO21-REP-BRIEFING-FIRST-RUN-PROOF`

## Reporting Rule

Operations reports create queue candidates.

They do not patch code, edit business data, restart automations, or talk directly to Luke unless the Rep turns their evidence into a clear decision.
