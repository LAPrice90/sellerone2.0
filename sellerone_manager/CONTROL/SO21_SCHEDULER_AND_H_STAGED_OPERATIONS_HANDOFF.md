# SO21 Scheduler And H Staged Operations Handoff

Created: 2026-06-09
Role: Rep handoff to Operations

## Instruction

Luke approved putting the next control sequence through.

Use `CONTROL/SO21_SCHEDULER_AND_H_STAGED_EXECUTION_PLAN.md` as the plan.

## Priority Order

### 1. Task Scheduler New-Style Review

Job: `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW`

Outcome required:

- classify every visible SellerOne-related Windows scheduled task into the new SellerOne 2.1 style
- write the review under `CONTROL/`
- do not change Task Scheduler

Classifications to use:

- Business Runtime
- Control Desk Automation
- Maintenance Protected
- retire or legacy candidate
- needs redesign

### 2. H Staged Retention Dry-Run Design

Job: `SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN`

Outcome required:

- design the safe dry-run route for H staged data
- define owner-proof checks
- define current/protected/failed-partial/audit/duplicate-candidate categories
- define graphs Luke should see before any approval
- do not delete, move, compress, purge, archive, run H, change pricing, or touch runtime

### 3. Customer-Style Proposal

After both reports exist and pass review, create a short proposal report for Luke:

- measured findings
- business case
- risk
- recommendation
- graph suggestions or graph outputs where measured data exists
- approve / hold / reject decision box

## Protected Boundary

Do not perform:

- Task Scheduler changes
- runtime pause or restart
- process kill
- worker restart
- deletion
- movement
- compression
- purge
- archive apply
- H run
- price change
- Google Sheets write
- database write or alignment
- queue edit outside approved status updates
- Amazon/security action
- purchase, receiving, or send-to-Amazon

## Blocker Rule

If any protected action is needed, stop and record:

- affected job
- what was attempted
- what failed or is blocked
- safest proposed fix
- whether Luke decision is needed
