# SellerOne 2.1 Queue Contract

Job: `SO21-QUEUE-CONTRACT`

Generated: 2026-06-08

## Plain-English Decision

The queue is now the centre of SellerOne engineering work.

Luke talks to the Rep. The Rep turns decisions into queue items. Builders work one ticket. Reviewers prove or return that ticket. Operations and Custodian reports create ticket candidates, not chat noise.

This contract does not change business runtime. It defines how SellerOne control work is owned.

## Canonical Queue

The canonical engineering queue is the approved task packet system.

The queue is made from:

- human-readable packet markdown under `sellerone_manager/tasks/`
- the generated packet index at `out/systems/M/approved_task_packets.csv`
- MOT evidence under `out/systems/M/mot/` when promoted into packets

The queue is not:

- chat history
- prompt folders
- the Manager Task Board
- the Manager Briefing UI
- `CODING_PLAN.md`
- `current_state.json`
- old plan folders
- paused automations

## Queue Folders

| Folder | Meaning | Queue Role |
|---|---|---|
| `sellerone_manager/tasks/proposed` | Draft or candidate work | Not active until approved |
| `sellerone_manager/tasks/approved` | Approved non-Luke work | Active queue source |
| `sellerone_manager/tasks/blocked` | Work needing Luke or protected approval | Blocked queue source |
| `sellerone_manager/tasks/archive` | Completed or retired packet history | Historical record |

Legacy placeholder folders:

- `sellerone_manager/tasks/done`
- `sellerone_manager/tasks/in_progress`
- `sellerone_manager/tasks/rejected`

Contract:

- keep these as historical placeholders until cleanup
- do not use them for new 2.1 queue movement

## Generated Index

File:

- `out/systems/M/approved_task_packets.csv`

Purpose:

- machine-readable index for Task Board, Manager Briefing, and packet claim/status commands

Contract:

- generated index only
- do not hand-edit it
- refresh it through the manager app
- if it disagrees with packet markdown, stop and open a queue reconciliation ticket

Current observed index counts:

| Status | Count |
|---|---:|
| approved | 10 |
| fixed_needs_retest | 1 |
| blocked_needs_luke | 4 |
| parked | 9 |
| proved | 108 |

Known current oddity:

- 2 proved rows still point to `tasks/blocked`.

Contract:

- treat this as an archive/cleanup issue, not a live blocker.
- do not move those files during this contract unless a separate cleanup ticket approves it.

## MOT Worklist

File:

- `out/systems/M/mot/mot_worklist.csv`

Purpose:

- independent evidence and candidate worklist

Contract:

- MOT worklist is not the canonical queue by itself.
- MOT rows become canonical only when converted or refreshed into task packets.
- MOT must remain an inspector. It must not patch outputs, hide failures, or silently change business data.

Observed MOT source statuses:

| MOT Status | Meaning In 2.1 |
|---|---|
| new | candidate for ticket |
| assigned | candidate already connected to a packet or owner |
| in_progress | evidence says work is active |
| fixed_needs_retest | candidate is waiting proof |
| retest_failed | candidate needs repair/reopen |
| blocked_needs_luke | create or preserve blocked packet |
| parked | not active until condition changes |
| proved | historical/evidence only |

## Source-Of-Truth Priority

When sources disagree, use this order:

1. Protected Luke decision captured in a durable file.
2. Latest direct proof artifact for the flow.
3. Latest MOT evidence for health truth.
4. Approved task packet markdown for scope and boundaries.
5. Generated packet index for current queue status.
6. `CONTROL/CURRENT_STATE.md` for human-readable summary.
7. Manager briefing and Task Board as read-only views.
8. `CODING_PLAN.md`, old plans, prompt folders, and chat history as context only.

Important rule:

- If a Luke decision exists only in chat, the Rep must write it into a durable packet, ADR, or current-state note before it drives work.

## Status Contract

SellerOne 2.1 uses the existing packet status vocabulary first.

### `proposed`

Meaning:

- idea or candidate work

Allowed owner:

- Rep
- Operations report
- Custodian report

Allowed next statuses:

- `approved`
- `blocked_needs_luke`
- `parked`
- archive/delete only by explicit cleanup ticket

### `approved`

Meaning:

- safe non-Luke work is ready to claim

Allowed owner:

- Builder

Allowed next statuses:

- `in_progress`
- `blocked_needs_luke`
- `parked`

### `in_progress`

Meaning:

- one Builder owns it now

Allowed owner:

- Builder

Allowed next statuses:

- `fixed_needs_retest`
- `blocked_needs_luke`
- `parked`
- `reopened` only if the claim/proof chain needs reset

### `fixed_needs_retest`

Meaning:

- Builder says the change or repair is ready for proof

Allowed owner:

- Reviewer
- MOT proof path

Allowed next statuses:

- `proved`
- `retest_failed`
- `blocked_needs_luke`
- `parked`

### `retest_failed`

Meaning:

- proof failed and Builder work must continue

Allowed owner:

- Builder
- Reviewer

Allowed next statuses:

- `in_progress`
- `fixed_needs_retest`
- `blocked_needs_luke`
- `parked`

### `reopened`

Meaning:

- a proved or parked ticket became active again because new evidence contradicted it

Allowed owner:

- Rep
- Reviewer

Allowed next statuses:

- `in_progress`
- `fixed_needs_retest`
- `blocked_needs_luke`
- `parked`

### `blocked_needs_luke`

Meaning:

- work cannot safely continue without Luke or protected approval

Allowed owner:

- Luke
- Rep records decision

Allowed next statuses:

- `approved`
- `in_progress` only after explicit approval and safe boundary
- `parked`
- `proved` only when the decision path was completed and proof exists

### `parked`

Meaning:

- not actionable now, but not deleted

Allowed owner:

- Rep
- Reviewer
- Operations

Allowed next statuses:

- `reopened`
- `approved`
- `archive` after retention review

### `proved`

Meaning:

- proof path passed and the ticket no longer needs active work

Allowed owner:

- Reviewer
- Rep records final state

Allowed next statuses:

- `archive`
- `reopened` only if newer evidence contradicts the proof

### `archive`

Meaning:

- historical storage after active work ends

Allowed owner:

- Rep
- Custodian after policy exists

Allowed next statuses:

- `reopened` only by explicit Rep decision

## Role Ownership

### Luke

Owns:

- business decisions
- protected approvals
- final direction changes

Does not own:

- raw technical triage
- routine proof collection
- stale automation noise

### Rep

Owns:

- Luke-facing conversation
- ticket creation
- queue explanation
- writing Luke decisions into durable queue or ADR files
- deciding what enters the queue

Does not own:

- hidden code repair without a ticket
- running worker cycles
- raw automation spam

### Operations

Owns:

- reading MOT evidence
- reading automation state
- reading storage/token/scheduler/lock reports
- creating operational ticket candidates
- summarising evidence for the Rep

Does not own:

- direct Luke conversation
- protected actions
- business runtime changes

### Builder

Owns:

- one ticket at a time
- scoped inspection
- scoped code/config/control changes
- focused tests
- moving ticket to `fixed_needs_retest`

Does not own:

- scope widening
- protected actions
- declaring proof complete without review

### Reviewer

Owns:

- fresh-context check
- proof validation
- moving ticket to `proved` or `retest_failed`

Does not own:

- relying on Builder chat history alone
- changing business state to make proof pass

### Custodian

Owns:

- lifecycle policy
- disk/token/log/archive/temp/stale/dead cleanup candidates
- preview-only cleanup until policy approval

Does not own:

- silent deletion
- protected business data changes

## Queue Movement Rules

1. A fuzzy request becomes `proposed` or a direct `approved` packet only if scope is clear.
2. A protected request becomes `blocked_needs_luke` until Luke approves the exact protected action.
3. A Builder claims only `approved`, `reopened`, or `retest_failed` packets.
4. A Builder never claims more than one ticket at a time.
5. A Builder moves work to `fixed_needs_retest`, not directly to `proved`.
6. A Reviewer or named proof path moves work to `proved`.
7. Failed proof becomes `retest_failed`, not a new duplicate ticket.
8. Work that cannot proceed safely becomes `parked` or `blocked_needs_luke`.
9. Done work is not deleted. It moves toward archive after the archive policy exists.
10. MOT worklist rows become queue items only through packet refresh or explicit Rep action.

## Source Conversion Rules

### From MOT

MOT `new`, `assigned`, `in_progress`, `fixed_needs_retest`, and `retest_failed` rows may become active packets.

MOT `blocked_needs_luke` rows must become blocked packets.

MOT `proved` and `parked` rows remain evidence unless a Rep opens or reopens a packet.

### From Operations Reports

Operations reports may create candidates for:

- stale automation
- stale scheduler
- dead lock
- storage threshold
- token usage spike
- repeated MOT fail

They do not run repairs directly.

### From Chat

Chat may start an idea.

Before work begins, the idea must be converted into:

- a task packet
- an ADR
- a current-state note

## View Rules

### Manager Task Board

Role:

- visual front desk

Contract:

- read-only
- not source of truth
- no card moves
- no task status edits
- no worker runs
- no protected approvals

### Manager Briefing

Role:

- Luke-facing summary

Contract:

- read-only
- hides raw paths and proof details unless requested
- should eventually read `CURRENT_STATE.md` or direct evidence instead of relying on stale JSON

## Archive Rules For Now

`tasks/archive` exists as the 2.1 archive folder.

Until `SO21-CUSTODIAN-POLICY` is complete:

- do not bulk move proved packets
- do not delete packet files
- do not purge old plans
- do not remove old prompt folders

Allowed now:

- create archive folder
- write README/policy marker
- list archive candidates

## Current Contract Gaps

### Gap 1 - No Current-State Generator

`CURRENT_STATE.md` exists but is manually written right now.

Needed:

- `SO21-CURRENT-STATE-GENERATOR`

### Gap 2 - Board Status Lanes Do Not Include Every Packet Status

The packet engine allows `reopened`; the current Task Board lanes do not visibly list it.

Needed:

- small UI/board contract update after queue contract is accepted

### Gap 3 - Proved Packets Still In Blocked Folder

Two proved index rows currently point to `tasks/blocked`.

Needed:

- archive cleanup ticket after Custodian policy

### Gap 4 - `CODING_PLAN.md` Is Still Bridge Memory

`CODING_PLAN.md` still carries active history while 2.1 control files are being created.

Needed:

- split active tickets into `CURRENT_TICKETS.md`
- move backlog into `BACKLOG.md`
- archive older proof history

## Acceptance Criteria

`SO21-QUEUE-CONTRACT` is complete when:

- this contract exists
- `tasks/archive` exists
- status meanings are written down
- source-of-truth priority is written down
- MOT-to-packet conversion is written down
- role ownership is written down
- no runtime business changes were made

## Result

`SO21-QUEUE-CONTRACT` is complete as a control document.

The next best task is `SO21-CURRENT-STATE-GENERATOR` or `SO21-CUSTODIAN-POLICY`.

Recommendation:

- do `SO21-CURRENT-STATE-GENERATOR` first, because Rep needs a reliable state file before Custodian and automation reports start feeding ticket candidates.
