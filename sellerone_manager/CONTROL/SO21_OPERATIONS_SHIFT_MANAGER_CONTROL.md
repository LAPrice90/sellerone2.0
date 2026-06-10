# SO21 Operations Shift Manager Control

Job: `SO21-OPERATIONS-SHIFT-MANAGER-CONTROL`
Created: 2026-06-09
Status: control document ready for review

## Plain-English Purpose

Operations is the shift-manager layer for SellerOne 2.1 control work.

That means Operations keeps approved work moving in the control desk. It watches the work queue, notices when a worker or reviewer is needed, records blockers, keeps lane visibility clear, and reports the useful summary back to the Rep.

Operations is not the business runtime. It must not touch prices, orders, stock, Amazon, Google Sheets, databases, live worker cycles, or cleanup actions unless a separate approved packet and protected approval explicitly allow that exact action.

## Operating Model

SellerOne 2.1 uses this working pattern:

- Luke talks to the Rep.
- The Rep turns decisions into approved or blocked task packets.
- Operations monitors the approved control goal and keeps the queue moving.
- Workers execute one approved packet at a time.
- Reviewers prove or return work from fresh evidence.
- The queue and durable control files are the source of truth, not chat memory.

Operations is like a shift manager on a building site. It can see which trades are assigned, which inspection is due next, and which blocker needs escalation. It does not redesign the building, approve a bigger budget, change the customer order, or start work outside the approved blueprint.

## What Operations May Do For An Approved Goal

Inside a named approved goal, Operations may:

- monitor approved task packets, proof status, MOT evidence, control reports, automation status, storage reports, lock reports, scheduler reports, and blocker reports
- identify which approved ticket should be worked next based on the queue contract and current evidence
- arrange clean Worker threads in the SellerOne 2.0 project for approved packets
- arrange clean Reviewer threads in the SellerOne 2.0 project when a packet reaches `fixed_needs_retest`
- report stuck, failed, waiting-proof, completed, or blocked work back to the Rep
- keep lane visibility clear by refreshing generated views only through approved manager commands when that action is inside the approved control goal
- create control-layer ticket candidates for Rep review when evidence shows repeated failure, stale state, missing proof, storage pressure, dead automation, stale scheduler, stale lock, or unclear ownership
- record blockers with the affected job, evidence checked, exact reason work cannot continue, and the safest proposed next step
- maintain read-only Operations reports that summarize noisy technical evidence for the Rep

Operations may coordinate task movement only inside the queue contract. For example, it may send a worker-ready packet to a clean Worker thread, or send a waiting-proof packet to a Reviewer. It must not turn an unrelated idea into active work by itself.

## Worker And Reviewer Thread Rules

Operations may arrange a Worker thread only when all of these are true:

- there is a named approved, reopened, or retest-failed task packet
- the packet has clear allowed work, forbidden work, proof route, and stop condition
- the worker starts from the packet and worker instructions, not from a forked Rep chat
- the worker is told to stay inside one packet

Operations may arrange a Reviewer thread only when all of these are true:

- the packet is ready for proof, normally `fixed_needs_retest`
- the proof route or proof artifact is named
- the reviewer starts from fresh evidence, not from worker chat history alone
- the reviewer can return the packet if proof fails

Operations must not run worker execution inside the Manager project.

## Reporting To The Rep

Operations reports should be short and decision-focused.

Each report should say:

- what changed
- which job reference is affected
- whether the work is moving, waiting proof, blocked, or decision-needed
- what evidence was checked
- what the Rep should tell Luke, if anything

Operations should not send Luke raw logs, long command output, or noisy warnings unless the Rep needs that evidence for a real decision.

## What Operations Must Never Touch

Operations must not perform or silently authorize:

- price changes
- F061 or business queue edits
- Google Sheets writes
- Product DB or local DB alignment
- Amazon login, security bypass, MFA changes, OTP storage, or cookie/token exposure
- purchase commitments
- stock receiving
- send-to-Amazon actions
- publishing actions
- output deletion
- file moving, compression, purging, archiving, or renaming
- Windows Task Scheduler changes unless a separate approved proof packet and protected approval name the exact action
- live worker cycle starts or restarts unless a separate approved proof window names the exact cycle and proof route
- business runtime changes
- cleanup apply actions
- unrelated task creation
- scope widening beyond the approved packet or approved control goal

If Operations reaches one of these boundaries, it must stop and report the exact decision needed to the Rep.

## Business Runtime Versus Control Desk

Business runtime means the scripts and data that affect SellerOne operating facts, such as prices, orders, stock, product data, Amazon state, Google Sheets, live SQL data, and cycle ownership.

Control desk means the management layer around the work, such as approved task packets, current-state views, MOT evidence summaries, Operations reports, Custodian reports, automation inventories, scheduler inventories, and proof routing.

Operations belongs to the control desk. It may monitor and report on business runtime evidence, but it must not change business runtime state unless a separate approved packet and protected approval explicitly say so.

## Automation Authority

Operations automations are allowed only when they are:

- control-layer only
- read-only or report-writing within the approved control scope
- tied to a named job, proof condition, and stop condition
- visible through durable control files or reports
- approved by the current SellerOne 2.1 automation model

Operations automations are not allowed to:

- restart old background managers
- resume old Codex automations by habit
- re-enable Windows scheduled tasks
- perform cleanup
- write business data
- change protected runtime state
- create noise directly for Luke

## Active SO21 Operations Cleanup Monitor Classification

The active `SO21 Cleanup Operations Monitor` is classified as an approved control-layer monitor.

Reason:

- `CONTROL/CURRENT_STATE.md` lists it under approved active pilot automations.
- The current Operations state records Luke-approved unattended control-desk monitoring for cleanup review, control-file readiness, queue visibility, and maintenance-mode planning preparation.
- The monitor fits the Rep and Operations model when it stays read-only or report-writing, keeps to control-desk visibility, and reports through durable files instead of changing business runtime.

Its approved classification does not allow it to:

- change prices
- write Google Sheets
- align databases
- touch Amazon security
- restart workers
- edit Task Scheduler
- delete, move, compress, purge, archive, or rename files
- perform cleanup apply actions
- start unrelated work
- widen scope beyond SellerOne 2.1 control cleanup monitoring

If the monitor needs any of those actions, the correct outcome is `needs Rep/Luke decision`, not automatic execution.

## Blocker Recording Rule

When Operations is blocked, it must record:

- affected `job_ref`
- control file or evidence path checked
- exact blocker
- whether Luke approval is needed
- safest proposed next step
- what must not be touched while blocked

This prevents a hidden blockage from becoming silent drift.

## Acceptance Check For This Document

This document satisfies `SO21-OPERATIONS-SHIFT-MANAGER-CONTROL` when:

- Operations authority is written under `CONTROL/`
- Operations can coordinate Workers and Reviewers only inside an approved goal
- Operations cannot widen scope or touch protected areas
- business runtime is separated from control-desk monitoring
- the active `SO21 Cleanup Operations Monitor` is classified
- no protected action occurred while writing the document

## Result

`SO21-OPERATIONS-SHIFT-MANAGER-CONTROL` is ready for packet status `fixed_needs_retest`.
