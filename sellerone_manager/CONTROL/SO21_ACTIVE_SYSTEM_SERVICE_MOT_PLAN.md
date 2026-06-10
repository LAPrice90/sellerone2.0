# SO21 Active System Service MOT Plan

Created: 2026-06-08
Status: planning

## Plain-English Purpose

Before moving on, SellerOne should service and MOT the parts of the management system that are still live.

This is not a rebuild. It is a structured check that the active control desk is clean, understandable, safe, and not still depending on old muddy process files.

## Scope

Review only what SellerOne is still using:

- Rep chat operating model
- Operations monitor
- current control files
- approved and blocked task packets
- queue refresh and current-state generation
- runtime-control and maintenance-mode plans
- read-only status design
- maintenance-record spec
- active Codex control automations
- worker/reviewer handoff pattern
- overnight/restart recovery rules

## Out Of Scope

Do not use this ticket to:

- rewrite business runtime
- pause or restart runtime
- change Task Scheduler
- change Amazon login/security
- change prices, Sheets, databases, purchases, receiving, or send-to-Amazon
- delete files permanently
- implement new code

## Questions To Answer

- Is there one clear source of truth?
- Can Luke tell what is happening without reading technical noise?
- Can Operations keep work moving without creating chaos?
- Are Workers and Reviewers started from clean packets?
- Are old files clearly marked as history?
- Does maintenance mode stop unsafe work before it starts?
- Are pause/restart rules recorded and recoverable?
- Does every active job have an owner, proof route, and stop condition?
- Are there any duplicated or stale control files still confusing the process?

## Expected Output

Create a plain-English MOT report under `CONTROL/`.

The report should include:

- what is healthy
- what is fragile
- what should be retired
- what should be improved tomorrow
- what needs Luke decision
- recommended order of fixes

## Stop Condition

Stop before implementation, protected actions, runtime changes, scheduler changes, or permanent deletion.
