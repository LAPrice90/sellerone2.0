# SO21 Multi-Lane Team Operating Model

Updated: 2026-06-09 15:20 UK
Owner: Rep / Operations

## Purpose

SellerOne 2.1 must operate like a managed team of employees, not a single-file queue.

The goal is simple:

- approved safe work should keep moving
- one blocked job must not stop unrelated jobs
- Operations must dispatch workers and reviewers, not just observe
- Rep Chat stays clean for Luke
- every idle approved job must have a reason

## Core Rule

One worker per risky ownership area, but many safe workers across different lanes.

Plain English:

- Do not create two F owners.
- Do not create two workers touching the same live runtime.
- But do run separate safe jobs at the same time when they do not touch the same protected thing.

## Permanent Roles

Only two permanent management chats exist:

- Rep Chat: Luke-facing front desk
- Operations Chat: shift manager and dispatcher

Temporary execution chats:

- Worker Chat: one approved packet only
- Reviewer Chat: one proof/review only

No extra manager chats.

## Active Lanes

Operations must maintain a lane board with these lanes.

### Lane 1 - Emergency Runtime Lane

Use for one urgent live/runtime issue at a time.

Examples:

- F recovery
- controlled runtime maintenance
- blocked live proof

Rules:

- maximum 1 active worker per runtime flow
- no second owner
- no restart without maintenance/proof route
- blocker must be written immediately

### Lane 2 - Control Cleanup And Proof Lane

Use for control-layer work that does not touch live business runtime.

Examples:

- cleanup-to-blueprint
- proof closure rules
- control flow confirmation
- operations authority confirmation

Rules:

- safe to run in parallel with Lane 1
- writes CONTROL evidence only
- no runtime, Task Scheduler, prices, Sheets, databases, Amazon/security, or deletion

Recommended active count:

- 1 to 2 workers

### Lane 3 - Reviewer And Closure Lane

Use to close work already completed by workers.

Examples:

- review a report
- retest a packet
- close `fixed_needs_retest`
- confirm proof evidence

Rules:

- reviewers must not implement
- reviewers should not wait behind active builders unless proof is missing
- closure should be fast so completed work does not rot

Recommended active count:

- 1 to 2 reviewers

### Lane 4 - Read-Only MOT And Diagnosis Lane

Use for read-only checks that identify what is broken without changing runtime.

Examples:

- B MOT diagnosis
- H MOT diagnosis
- O readiness diagnosis
- queue movement review

Rules:

- read-only unless a separate approved repair packet exists
- one diagnostic per flow at a time
- no live restart, no business changes, no output deletion

Recommended active count:

- 1 to 2 workers across different flows

### Lane 5 - Planning And Proposal Lane

Use for tomorrow-ready business cases and improvement plans.

Examples:

- app professional-grade proposal
- data storage proposal
- automation improvement proposal

Rules:

- must produce decision-quality output
- graphs/proposals are allowed when requested
- no implementation unless separately approved

Recommended active count:

- 1 worker when capacity exists

## Dispatch Rules

Operations must classify every approved non-Luke packet as one of:

- active now
- safe to start next
- waiting proof/review
- blocked with reason
- parked with reason

Approved work must not be left idle without one of those labels.

Every Operations pass must do at least one of:

- close a waiting-proof item
- assign a safe worker
- assign a reviewer
- record a real blocker
- request a real Luke decision

## Minimum Team Shape

When there are enough approved safe packets, Operations should aim for:

- 1 emergency lane if needed
- 1 control/proof worker
- 1 reviewer
- 1 read-only diagnostic or planning worker

That means 3 to 4 useful lanes should normally be moving, unless evidence says they are unsafe.

Maximum default active load:

- 6 total temporary worker/reviewer threads
- only 1 active worker per live runtime flow
- no more than 2 reviewers at once unless there is a backlog of completed proof

## Stale Work Rule

Any active worker or reviewer with no visible result after one Operations cycle must be checked.

If still no movement after the next cycle, Operations must record one of:

- still working with reason
- blocked with exact blocker
- needs reviewer
- needs Luke decision
- safe to replace with a fresh worker

Silent waiting is not acceptable.

## Blocker Rule

A blocker stops only the affected lane.

Example:

- F stuck process blocks F runtime proof.
- It does not block SO21 control reports.
- It does not block reviewer closure.
- It does not block read-only MOT diagnosis for other flows.

## Proof Rule

Work is only completed when proof exists.

Proof can be:

- review note
- passing focused tests
- MOT retest
- redacted live proof
- decision report accepted as planning-only

Status labels alone are not proof.

## Tonight's Execution Standard

Tonight should not be judged by whether one stuck issue magically clears.

Tonight should be judged by:

- how many safe lanes moved
- which blockers were real
- which packets closed
- whether F has a clean recovery path
- whether approved work stopped sitting idle without a reason

## Tomorrow Morning Evidence

Rep should be able to tell Luke:

- how many lanes ran
- which tickets closed
- which tickets moved to proof/review
- which tickets are blocked and why
- whether any worker sat idle without a reason
- what the next highest-value action is

## Forbidden Without Separate Approval

- Amazon security bypass
- repeated SMS, phone, or code attempts
- price changes
- Sheet writes
- database alignment
- output deletion
- permanent Task Scheduler changes
- destructive cleanup
- second owner for the same live runtime
- unbounded runtime restarts
