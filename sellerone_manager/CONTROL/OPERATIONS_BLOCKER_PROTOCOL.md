# Operations Blocker Protocol

Created UTC: 2026-06-08T17:55:26Z
Role: Operations

## Standing Rule

If Operations, a Worker, or a Reviewer hits a machine-level or access blocker, do not guess, silently skip, or keep retrying blindly.

Record the blocker clearly for Rep/Luke.

## Blockers Covered

- Windows permissions
- locked files
- Task Scheduler access limits
- missing credentials
- app connector limits
- machine-level restrictions
- protected-boundary conflicts

## Required Blocker Record

Every blocker report must include:

- affected job
- what was attempted
- what failed
- evidence or error summary
- safest proposed fix
- whether Luke approval is needed

## Protected Boundary

This protocol does not approve retries, permission escalation, credential handling, Task Scheduler changes, runtime changes, queue edits, Amazon login/security action, deletion, movement, compression, purge, archive apply, price changes, Sheet writes, or database writes.

## Current Use

This rule applies immediately to SellerOne 2.1 cleanup management, including the review threads for:

- `SO21-LEGACY-CONTROL-APPLY-PLAN`
- `SO21-RUNTIME-MAINTENANCE-CONTROL-REVIEW`
