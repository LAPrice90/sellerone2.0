# SO21 Maintenance Mode Implementation Plan

Created: 2026-06-08
Status: planning path

## Plain-English Decision

SellerOne maintenance mode should work like a managed breaker panel, not a panic kill button.

The goal is to let Codex and Operations work safely without manually hunting through Windows Task Scheduler every time, while still protecting the live business.

## Current Position

Maintenance planning has started, but the runtime map is not yet trusted as live state because a fresh read-only scheduler check found that older pause evidence is stale.

Current foundation evidence:

- `CONTROL/RUNTIME_CONTROL.md`
- `CONTROL/SO21_RUNTIME_MAINTENANCE_SCHEDULER_STATE_BLOCKER.md`
- `CONTROL/SO21_SCHEDULER_STATE_RECONCILIATION.md`

## Key Rule

Do not build or use a blind process kill switch.

Future maintenance control should use:

- read-only status first
- clear task classification
- a maintenance request record
- soft pause where the process supports it
- recorded restart instructions
- health proof after exit

Hard process termination should remain a protected last-resort action.

## How It Should Work When A Cycle Needs Work

### 1. Decide The Work Type

Before touching a cycle, Operations classifies the work:

- code-only work that does not touch live outputs
- read-only proof work
- output or ownership maintenance
- runtime pause needed
- runtime restart needed

If the work is code-only or read-only, maintenance mode may not be needed.

If the work could clash with an active cycle, maintenance mode is requested.

### 2. Check Runtime Classification

The target is checked against runtime control:

- Business Runtime: may now be included in controlled maintenance pause/restart only when a maintenance record names the exact target, reason, restart route, and proof route.
- Control Desk Automation: can eventually be paused/restarted by Operations after approved design.
- Maintenance Protected: never touched until classified.

### 3. Use A Maintenance Record

Every future maintenance session should write a record before it changes anything.

The record should include:

- job reference
- target cycle or automation
- reason
- requested action
- approval source
- expected duration
- what may be paused
- what must not be touched
- rollback path
- exit and restart method

This prevents "we think we paused X" confusion later.

### 4. Prefer Soft Pause Over Kill

The preferred future design is a code-level soft maintenance switch.

That means a cycle checks a safe marker before starting or at safe checkpoints. If maintenance is active, it should:

- avoid starting new work
- finish or park safely at a known checkpoint
- write why it parked
- avoid reading half-finished outputs

This is safer than killing a process mid-write.

### 5. Hard Kill Is Protected

Killing a live process can leave half-written files, stale locks, missing proof, or false health failures.

Hard kill may only be considered when:

- the process is proven stuck or unsafe
- the affected runtime is classified
- the exact action is approved
- rollback and recovery are written down

## Restart Design

Restart must come from the maintenance record, not memory.

Exit maintenance should:

1. Read the maintenance record.
2. Restart only the items that record says were paused.
3. Use the approved restart route for that item.
4. Run the named health checks.
5. Record the exit result.

For Control Desk Automations, this may eventually be a Codex automation restart or heartbeat update.

For Business Runtime, restart remains approval-gated and should use the approved runtime owner route, not an ad hoc command.

## Phased Build Plan

### Phase 1 - Read-Only Runtime Status

Purpose:

- show current scheduler, automation, lock, owner, and maintenance-marker state
- change nothing
- give Operations a trusted dashboard before any switch exists

Deliverable:

- design and later build `runtime_status` as read-only

Rules:

- no pause
- no restart
- no Task Scheduler change
- no runtime change

### Phase 2 - Maintenance Record Design

Purpose:

- define the record that says what is being maintained, why, and how it exits

Deliverable:

- maintenance request and active maintenance record format

Rules:

- planning only first
- no cycle changes yet

### Phase 3 - Control Desk Automation Soft Pause

Purpose:

- let Operations pause and resume read-only control automations safely

Examples:

- cleanup monitor
- Rep briefing pilot
- control reports

Rules:

- control-desk only
- no business runtime
- all pause/resume actions must be recorded

### Phase 4 - Cycle Soft-Pause Design

Purpose:

- teach selected cycles to respect a maintenance marker at safe boundaries

Examples:

- before starting a run
- before writing outputs
- before restarting child work
- before reading a file known to be under maintenance

Rules:

- design and review first
- business runtime pause authority still needs Luke approval

### Phase 5 - Approved Business Runtime Maintenance Windows

Purpose:

- allow a named, time-limited maintenance window for a specific business cycle when needed

Rules:

- exact cycle named
- exact action named
- exact restart route named
- exact proof route named
- Luke approved controlled pause/restart authority on 2026-06-08
- every use must still be recorded before action and proved after restart

## Tickets To Carry Forward

Recommended active/control tickets:

- `SO21-RUNTIME-CONTROL-SCHEDULER-STATE-ADDENDUM`
- `SO21-RUNTIME-STATUS-READONLY-DESIGN`
- `SO21-MAINTENANCE-RECORD-SPEC`
- `SO21-CONTROL-DESK-MAINTENANCE-SWITCH-DESIGN`

Authority decision now recorded:

- `SO21-BUSINESS-RUNTIME-MAINTENANCE-AUTHORITY`
- `CONTROL/SO21_BUSINESS_RUNTIME_MAINTENANCE_AUTHORITY.md`

## Current Recommendation

Do Phase 1 and Phase 2 next, then design the controlled maintenance switch.

Do not use pause/restart scripts until the switch, record handling, restart route, and health proof have been reviewed.

## Overnight Test Note - 2026-06-08

Luke requested quiet-hours testing while the PC is expected to restart at 02:00 UK on 2026-06-09.

The approved overnight test plan is `CONTROL/SO21_OVERNIGHT_CONTROL_TEST_PLAN.md`.

Overnight testing must stay read-only or planning/control-only and must not start any check that could be left half-finished across the 02:00 restart.
