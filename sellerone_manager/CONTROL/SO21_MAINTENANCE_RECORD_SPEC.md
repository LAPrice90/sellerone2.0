# SO21 Maintenance Record Spec

Job: `SO21-MAINTENANCE-RECORD-SPEC`
Created: 2026-06-08
Mode: design only

## Plain-English Purpose

Maintenance mode needs a written record for every maintenance session.

The record is the handrail. It says what was requested, what was approved, what was paused, how it should restart, and what proof is needed before the work is trusted.

## Core Rule

Restart must come from the maintenance record, not memory.

If the record does not say an item was paused, exit maintenance must not restart it.

## Record Types

### Maintenance Request

Created before maintenance begins.

Required fields:

- record id
- created time
- requested by
- job reference
- target cycle or automation
- reason
- expected duration
- affected files or outputs
- requested action
- classification: Business Runtime, Control Desk Automation, or Maintenance Protected
- approval source
- protected boundaries
- stop conditions

### Active Maintenance Record

Created when maintenance actually starts.

Required fields:

- record id
- start time
- approved scope
- exact pause method
- exact targets paused
- targets explicitly not paused
- current scheduler or automation state before change
- rollback path
- worker or reviewer owner
- expected proof route

### Exit Record

Created when maintenance ends.

Required fields:

- record id
- end time
- work completed
- restart method used
- targets restarted
- targets not restarted
- health checks run
- proof result
- unresolved follow-ups
- remediation path if proof fails

## Allowed Future States

- requested
- approved
- active
- exiting
- closed
- blocked
- cancelled

## Business Runtime Rule

Business Runtime cannot move from requested to active without explicit authority for the exact target and action.

This includes:

- orders
- pricing
- F scanner
- H cycle
- restart chain
- any task marked Business Runtime in `RUNTIME_CONTROL.md`

## Control Desk Automation Rule

Control Desk Automation may eventually be paused or resumed by Operations, but only after the control-desk maintenance switch is designed, reviewed, and approved.

## Maintenance Protected Rule

Maintenance Protected items cannot be paused, killed, restarted, enabled, disabled, or edited until they are classified by a separate approved packet.

## Soft Pause Preference

Future cycle maintenance should prefer a soft pause marker at safe boundaries.

The cycle should avoid starting new work or should park safely instead of being killed mid-write.

## Hard Kill Rule

Hard process kill is protected.

It requires exact approval, a recovery path, and proof that waiting or soft pause is not safe enough.

## Success Criteria

This spec is ready for review when:

- request, active, and exit records are defined
- restart is tied to the record
- Business Runtime remains approval-gated
- Control Desk Automation is separated from Business Runtime
- Maintenance Protected items cannot be touched

## Current Next Move

Review this spec, then design the control-desk maintenance switch.
