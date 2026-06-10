# F Named Owner Stop Handoff Approval

Created: 2026-06-09 22:42 UK
Owner: Rep / Operations
Status: approved inside F emergency boundary

## Plain-English Decision

F is still not finished.

Waiting indefinitely for the current F owner to drain is not acceptable tonight.

Luke has already approved controlled pause/restart authority for named cycle work, and F is the named emergency task.

This record confirms that Operations may use a named F-only stop/handoff route for the current F owner if that owner is alive with no progress and no safe drain marker.

## Current Reason

Latest evidence says:

- A is not blocking F now
- shared maintenance markers are clear
- `AMZ Pricing Summary Hourly` is disabled for the F emergency window
- daily `AMZ Pricing Summary` remains enabled and ready for 06:00
- F owner is alive but no progress is being made
- F controller remains blocked at `normal_scan_only` / `attempt_mode_not_enabled`
- Dashboard Yes/No is not proved
- logged-out parked-and-moving is not proved

## Approved Scope

Approved only for F:

- identify the current F owner PID from live lock/supervisor evidence
- use the softest available F-owned stop/handoff route first
- if a graceful F-owned route exists, use it
- if the owner cannot drain or hand off, record the exact stronger action needed before using it
- after handoff, run the bounded F proof route
- prove either Dashboard Yes/No or logged-out parked-and-moving

## Required Proof

Operations must record:

- old owner PID
- stop/handoff method used
- whether a new owner was created
- controller state after handoff
- Dashboard Yes/No result, or logged-out parked-and-moving result
- whether `AMZ Pricing Summary Hourly` remains safely held or restored
- daily A 06:00 task remains untouched

## Forbidden

Do not:

- create a second F owner before the old owner is cleared
- use a separate Chrome workaround
- bypass Amazon security
- repeat SMS/phone/code attempts
- change prices
- write Sheets
- align databases
- delete outputs
- place orders
- receive stock
- send anything to Amazon
- touch daily A
