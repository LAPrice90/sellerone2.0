# SO21 Business Runtime Maintenance Authority

Created: 2026-06-08
Status: Luke approved controlled pause/restart authority

## Plain-English Decision

Luke approved pause/restart authority for maintenance mode.

This approval is not a blank kill switch. It allows SellerOne to design and use controlled maintenance pause/restart only when the target, reason, approval source, restart method, and proof route are written into a maintenance record.

## Approved Authority

Operations may proceed with a controlled pause/restart model for named maintenance work.

Allowed only when all of these are true:

- the target is named
- the reason is named
- a maintenance request exists
- a maintenance record exists before action
- the record says exactly what may be paused
- the record says exactly how it should restart
- health proof is required after restart
- any blocker is logged clearly

## Still Not Approved As A Blank Action

This approval does not allow:

- blind process killing
- permanent Task Scheduler edits
- permanent deletion
- Amazon login/security bypass
- price changes
- Google Sheets writes
- database writes or alignment
- purchase, receiving, or send-to-Amazon actions
- queue edits outside approved status updates

## Business Runtime Scope

Business runtime may be included in a maintenance window only through the maintenance record.

Examples:

- Orders
- Pricing
- F scanner
- H cycle
- restart chain

## Preferred Method

The preferred method is soft pause first:

- stop starting new work
- park at safe checkpoints
- avoid reading or writing half-finished outputs
- record the park reason

Hard kill remains a last-resort action and must be explicitly justified in the maintenance record.

## Restart Rule

Restart must come from the maintenance record.

If the maintenance record does not say something was paused, exit maintenance must not restart it.

## Luke Clarification - 2026-06-09

When Luke approves a named task for a cycle, that approval includes controlled pause and restart authority for that same named cycle when the pause/restart is needed to complete the approved repair, proof, or addition.

This is not a blank kill switch.

Rules:

- the target cycle must be named
- the reason must be tied to the approved task
- Operations must use the softest safe pause/reload method available
- Operations must not create a second owner
- Operations must not leave the cycle stopped
- restart or relaunch proof is mandatory
- post-restart health proof is mandatory
- if restart fails, Operations must record the blocker and alert the Rep

Plain English: giving a job on a named cycle gives permission to pause and restart that cycle if the work genuinely needs it, but the system must prove it was restarted cleanly.

Longer-term scheduling note:

- Some business areas may need working-hour limits, for example avoiding repricer work during peak sales windows.
- Other areas, such as price-list scanner maintenance, may be less time-sensitive and can be worked on during broader windows.
- Future maintenance planning should classify cycles by safe working windows before routine maintenance automation is expanded.

## Expected Next Work

Create or continue planning/build tickets for:

- controlled maintenance switch design
- business-runtime maintenance guardrails
- runtime-status read-only build
- maintenance-record implementation

No state-changing pause/restart script should be used until reviewed and proved.
