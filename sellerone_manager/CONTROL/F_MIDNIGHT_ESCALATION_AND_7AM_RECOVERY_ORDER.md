# F Midnight Escalation And 7am Recovery Order

Created: 2026-06-09 16:18 UK
Owner: Rep / Operations
Status: Luke approved priority order

## Plain-English Order

F cycle must be treated as tonight's emergency business priority.

Anything short of F being finished before midnight is unacceptable from a business point of view.

## Business Reason

F is blocking SellerOne growth and restocking progress.

Luke is losing money while F sits stuck, so other work must not be allowed to quietly consume the night if F is still unfinished.

## Finish Definition

F is only finished when one of these is proved:

- Seller Central login is alive through the rebuilt single controller and F can continue normally, or
- Seller Central is unavailable but F parks the blocked supplier cleanly, moves to the next price file, and has a proved return path.

F is not finished just because:

- a worker says code changed
- a status file says logged in
- BBP auth works
- TD Synnex remains stuck at the same point

## Immediate Priority

Operations must keep F as the emergency lane.

The current blocker is `AMZ Pricing Summary Hourly`, not the normal 06:00 A cycle.

Luke has approved a temporary bounded hold/pause of `AMZ Pricing Summary Hourly` for the F proof window, with restore/proof required afterwards.

## Midnight Rule

If F is not finished by 2026-06-10 00:00 UK:

- put non-F jobs on hold
- do not start new non-F workers
- keep only work that directly helps F, runtime recovery, or mandatory morning recovery
- record exactly what remains blocking F
- continue F-focused work until it is finished or until a hard external blocker is proved

## 2am Restart Rule

The PC restart around 02:00 UK must be treated as a recovery risk.

Before the restart window, Operations must record:

- what was paused
- what must restart
- what must not restart
- how to confirm state after reboot

After the restart window, Operations must check the runtime state rather than assuming Task Scheduler restored everything correctly.

## 7am Recovery Rule

By 2026-06-10 07:00 UK:

- all approved business runtime that was intentionally paused must be restored or have a named blocker
- the normal daily A path must not be left broken
- F must be either running normally, finished by clean parking/continuation, or escalated with exact evidence
- Rep must be able to give Luke a plain-English morning status

## Forbidden Actions

Do not:

- change prices
- write Google Sheets
- align databases
- delete outputs
- place orders
- receive stock
- send anything to Amazon
- bypass Amazon security
- leave paused runtime without a restore/proof note
- permanently redesign scheduler ownership during the emergency proof window

## Reporting Required

Operations must report:

- F proof result
- whether `AMZ Pricing Summary Hourly` was held/paused
- whether it was restored
- whether the 02:00 restart changed runtime state
- morning recovery status by 07:00 UK
