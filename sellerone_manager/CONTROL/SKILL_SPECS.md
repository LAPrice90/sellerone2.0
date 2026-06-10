# SellerOne 2.1 Skill Specs

Job: `SO21-SKILL-SPECS`
Date: 2026-06-08

## Plain-English Status

SellerOne repeat workflows are now written as reusable skill or template specs.

These are not new automations yet. They are recipes. A future task can turn the useful ones into actual Codex skills, task templates, or small command helpers.

## Why This Exists

The old system repeated the same instructions across chats, prompt folders, role files, plans, and automations.

SellerOne 2.1 keeps the current rules in one place and turns repeated workflows into small reusable specs.

## Shared Rule For Every Skill

Every SellerOne skill or template must:

- read current control files first
- stay inside the approved role
- avoid protected actions
- write durable evidence instead of relying on chat memory
- produce one clear next step
- avoid raw log dumps unless they change a decision

Protected actions still need Luke:

- prices
- queues
- Google Sheets writes
- Product DB or local DB alignment
- output deletion
- worker restarts
- live worker cycles without approved proof window
- publishing
- purchase commitments
- receiving stock
- send-to-Amazon
- Amazon security changes
- automation restarts

## Spec 1 - SellerOne Rep Briefing

Purpose:

- turn current control evidence into a calm Luke-facing update.

Trigger:

- Luke asks for status, planning, priorities, or "what next?"

Reads:

- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`

Output:

- short plain-English manager briefing
- one recommended next move
- Luke action needed only when a protected decision is real

Forbidden:

- raw worker logs by default
- worker cycle starts
- queue edits
- protected business actions

Done when:

- Luke can understand status without reading technical artifacts.

## Spec 2 - SellerOne Builder Packet

Purpose:

- complete one approved manager task packet safely.

Trigger:

- Builder or Worker chat is opened for a specific approved packet.

Reads:

- `WORKER_CHAT.md`
- claimed approved task packet
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- named proof artifacts from the packet

Output:

- focused code or control-file change
- local proof result
- packet status update to `fixed_needs_retest` when ready

Forbidden:

- scope widening
- protected actions
- marking work proved without the named proof
- creating a separate task list

Done when:

- the packet's done-when proof has been run or the exact blocked proof is recorded.

## Spec 3 - SellerOne Reviewer Proof

Purpose:

- review one Builder result from fresh context.

Trigger:

- a packet enters review, `fixed_needs_retest`, or proof-ready state.

Reads:

- task packet
- code diff or control-file diff
- named proof artifacts
- current MOT output where relevant

Output:

- proved, returned, or blocked recommendation
- clear reason if proof does not pass

Forbidden:

- trusting Builder chat history as proof
- approving protected movement
- hiding stale health evidence

Done when:

- the proof route is checked and the packet has a clear next state.

## Spec 4 - SellerOne Custodian Report

Purpose:

- measure bloat, stale files, old logs, stale automations, and cleanup candidates without deleting anything.

Trigger:

- Luke asks about cleanup, disk growth, storage policy, old outputs, or dead automations.

Reads:

- `CONTROL/STORAGE_POLICY.md`
- `CONTROL/STORAGE_INDEX.csv`
- `CONTROL/OPERATIONS.md`
- relevant folder inventories

Output:

- dry-run manifest or cleanup candidate report
- protected exclusions
- rollback route

Forbidden:

- deletion
- moving protected files
- runtime data edits
- automation restarts

Done when:

- cleanup can be reviewed from a manifest before any destructive step.

## Spec 5 - MOT-To-Packet Promotion

Purpose:

- turn MOT candidate work into bounded approved task packets or blocked decisions.

Trigger:

- MOT finds new, repeated, or materially worse evidence.

Reads:

- `out/systems/M/mot/mot_latest.md`
- `out/systems/M/mot/mot_worklist.csv`
- `out/systems/M/approved_task_packets.csv`
- existing packet files

Output:

- approved packet, blocked packet, or parked note
- `job_ref`
- allowed scope
- forbidden actions
- proof route
- stop condition

Forbidden:

- treating MOT candidates as approved work without a packet
- changing business runtime
- hiding MOT failures

Done when:

- the work is visible in the queue and not duplicated in chat.

## Spec 6 - SellerOne Automation Rebuild

Purpose:

- rebuild only the small set of useful 2.1 automations after the control system is stable.

Trigger:

- Luke approves automation rebuild after queue, current state, skill specs, and Custodian policy exist.

Reads:

- `CONTROL/CURRENT_STATE.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/QUEUE_CONTRACT.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`

Output:

- proposed automation list
- purpose for each automation
- schedule
- destination control file
- protected boundaries

Forbidden:

- restarting old heartbeat managers blindly
- worker cycles
- business actions
- protected approvals

Done when:

- every automation has one clear purpose and writes to a control artifact.

## Spec 7 - Storage Subtree Index

Purpose:

- classify the mixed `out/` folder before any cleanup manifest exists.

Trigger:

- Custodian sees `STORAGE_INDEX.csv` still says `out/` needs subtree classification.

Reads:

- `CONTROL/STORAGE_POLICY.md`
- current `out/` subtree folders
- known runtime and proof paths

Output:

- updated storage index or subtree report
- protected live paths
- cleanup candidate classes

Forbidden:

- deletion
- moving files
- changing locks
- touching live databases
- editing proof outputs to improve status

Done when:

- `out/` is split into protected live data, proof history, logs, temp files, backups, and cleanup candidates.

## Conversion Rule

These specs are approved as design specs only.

Turning any spec into an installed Codex skill, automation, or command helper needs its own follow-up task.
