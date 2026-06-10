# SO21 Professional Grade Finalisation Plan

Created: 2026-06-08
Status: planning

## Plain-English Purpose

SellerOne has been built while learning the process at the same time.

Before finalising the build, the active system needs a professional-grade pass. This means making it easier to run, easier to recover, easier to explain, and harder to accidentally break.

This is not a feature wishlist. It is a finalisation checklist for the system we are still using.

## What Professional Grade Means Here

- one clear source of truth
- clean operating roles
- clear handoffs between Rep, Operations, Worker, and Reviewer
- repeatable maintenance mode
- restart/recovery records
- storage lifecycle and dedupe
- clear test and proof rules
- plain-English operating manual
- known risks and known limits
- no hidden dependency on old work logs or chat memory

## Recommended Finalisation Layers

### 1. Operating Manual

Create a short plain-English manual:

- how Luke uses the Rep chat
- what Operations does
- how Workers and Reviewers are started
- how tasks move through the queue
- when Luke is needed
- what must never happen automatically

### 2. Runbook

Create a practical runbook:

- daily health check
- what to do after PC restart
- what to do when a job is stuck
- what to do when Windows permissions fail
- how to enter and exit maintenance
- how to recover from a failed pause/restart

### 3. Source-Of-Truth Audit

Confirm the system ignores old files:

- `WORK_LOG.md`
- `CODING_PLAN.md`
- `plans/active`
- `project_control`
- old prompt archives

If they remain physically present, mark them clearly as history or extract only useful facts into current control files.

### 4. Test And Proof Matrix

Create a simple matrix:

- what is tested
- how it is tested
- what proof file shows it passed
- what failure looks like
- who owns the fix

### 5. Recovery And Rollback

Make sure every active process has:

- backup or rollback route
- restart route
- health proof
- stop condition
- owner

### 6. Data Lifecycle

Finish the Custodian data plan:

- inventory data families
- duplicate report
- retention rules
- dry-run cleanup
- safe automation design

### 7. Automation Register

Keep one live register of automations:

- name
- purpose
- owner
- cadence
- approved status
- pause/restart rule
- proof output

### 8. Risk Register

Keep one short risk list:

- current risk
- why it matters
- current mitigation
- next action
- Luke decision needed or not

### 9. Final Acceptance Checklist

Before calling the build final, confirm:

- old system cannot accidentally drive work
- Operations can keep work moving
- workers start clean
- reviewers verify proof
- maintenance mode is designed and tested
- data cleanup has rules
- restart recovery is documented
- Luke knows where decisions appear

## Stop Condition

Stop before implementation, protected runtime action, scheduler change, deletion, database write, Sheet write, Amazon/security action, or business action.
