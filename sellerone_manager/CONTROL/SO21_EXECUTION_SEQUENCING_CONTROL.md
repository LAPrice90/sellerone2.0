# SO21 Execution Sequencing Control

Created: 2026-06-08
Job: SO21-EXECUTION-SEQUENCING-CONTROL
Mode: planning-only control note

## Plain-English Purpose

This note is the traffic rule for SellerOne 2.1 cleanup and control planning.

The simple rule is: one primary cleanup/control worker changes the control system at a time. Read-only helpers may run beside that worker only when they are inspecting different files and do not share decision authority.

This is meant to stop two workers from editing the same blueprint at once.

## Default Execution Model

The default execution model is one primary active cleanup worker at a time.

A primary cleanup/control worker is any Worker that may write, repair, create, or update SellerOne 2.1 control files, planning files, packet files, or proof-control notes.

Only one primary worker should be active because overlapping writes can create false proof, unclear ownership, or duplicate management noise.

## Parallel Work Allowed

Read-only support jobs or review jobs may run in parallel only when all of these are true:

- they do not write to the same files as the primary worker
- they do not claim authority over the same packet, proof path, or control decision
- they do not run business runtime, scheduler, automation, worker restart, maintenance, database, Sheet, Amazon, price, stock, purchase, receiving, output cleanup, or destructive actions
- they report findings back through the Rep or the approved Operations control path

Examples of allowed parallel support:

- a Reviewer reading a finished packet and its proof artifact
- Operations reading existing status files to detect blockers
- Custodian measuring storage or listing cleanup candidates without deleting, moving, compressing, purging, archiving, or renaming anything

## Work That Must Wait

A job must wait for predecessor evidence when it depends on another job's completed control note, packet status, proof path, or blocker report.

The waiting job should not start write work until the predecessor has produced one of these clear outputs:

- a completed control note under `sellerone_manager/CONTROL/`
- a packet status that is ready for review or proof
- a proof artifact named by the approved packet
- a blocker record that explains why the predecessor cannot continue

Examples of work that must wait:

- cleanup apply work must wait for the cleanup policy, manifest, and approval path it depends on
- runtime maintenance control review must wait for the relevant planning or evidence note when that note defines the proof rule
- archive, purge, compression, deletion, or file movement work must wait for a separate approved cleanup packet and Luke-approved destructive action if required

## Operations Worker And Reviewer Creation

Operations may create the Workers and Reviewers needed for the approved goal when the goal already has a valid approved packet, proof route, and control boundary.

Operations must not create Workers or Reviewers for unrelated work, widened scope, protected actions, or speculative cleanup.

If a needed Worker or Reviewer would touch protected areas, Operations must report the need to the Rep instead of starting it.

## Blocker Reporting

If Operations, a Worker, or a Reviewer hits a blocker, do not guess, silently skip, or keep retrying.

Record the blocker for the Rep with:

- affected job
- what was attempted
- what failed
- evidence or error summary
- safest proposed fix
- whether Luke approval is needed

Covered blockers include Windows permissions, locked files, Task Scheduler access limits, missing credentials, app connector limits, machine-level restrictions, and protected-boundary conflicts.

## Completion Reporting

Completed work should be reported to the Rep with:

- job reference
- exact file or proof path created
- whether the work is ready for Reviewer proof
- any remaining gap or wait condition
- confirmation that no forbidden runtime, scheduler, automation, worker restart, destructive cleanup, price, Sheet, database, output, Amazon/security, maintenance pause/restart, or state-changing maintenance-script action occurred

Workers should not claim a task is proved just because a note was written. A separate Reviewer or named proof path must confirm proof if the packet requires it.

## Protected Boundary

This note does not approve:

- business runtime changes
- Task Scheduler changes
- Codex automation changes
- worker restarts
- queue widening
- file deletion, movement, compression, purging, archiving, or renaming
- price changes
- Google Sheets writes
- Product DB or local DB alignment
- Amazon login or security action
- maintenance pause or restart
- state-changing maintenance-script use

## Overnight Timing Rule

For the 2026-06-08 to 2026-06-09 overnight control window, do not start any new check after 2026-06-09 01:45 UK time that could be interrupted by the expected 2026-06-09 02:00 UK restart.

## Acceptance Check

This control note satisfies the SO21 execution sequencing packet when:

- this file exists under `sellerone_manager/CONTROL/`
- it states that the default model is one primary active cleanup worker at a time
- it allows read-only support or review jobs in parallel only when they do not overlap files or authority
- it states that Operations may create workers and reviewers needed for the approved goal, but not unrelated work
- no runtime or destructive action occurred
