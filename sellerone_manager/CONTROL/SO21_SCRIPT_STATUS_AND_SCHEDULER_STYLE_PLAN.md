# SO21 Script Status And Scheduler Style Plan

Created: 2026-06-08
Status: planning

## Plain-English Purpose

SellerOne needs a proper way to check whether important scripts are healthy.

At the moment, some checks are handled by Windows Task Scheduler and MOT-style reports, but the control desk does not yet have one clean view that says:

- which scripts are meant to run
- who owns them
- how often they should run
- what proof shows they worked
- what counts as stale or failed
- which scheduled tasks fit the new SellerOne 2.1 style
- which scheduled tasks are legacy noise

## Business Reason

Luke should not have to open Task Scheduler or dig through output folders to know if the system is alive.

Operations should be able to report script health in plain English and only involve Luke when a real decision or protected action is needed.

## Workstream A - Script Status Health Map

Create a map of active scripts/checks:

- script or launcher name
- purpose
- owner flow
- schedule or trigger
- expected proof output
- last successful proof
- stale threshold
- failure threshold
- who handles repair
- whether Luke approval is needed

## Workstream B - Task Scheduler Style Review

Review the visible Windows scheduled tasks and classify each into the new style:

- Business Runtime
- Control Desk Automation
- Maintenance Protected
- Retire / legacy candidate
- Needs rewrite into SellerOne 2.1 control automation

This is review-only first.

## Workstream C - New-Style Monitoring Design

Define how SellerOne should monitor script health going forward:

- read-only status checks first
- plain-English Operations summary
- no hidden auto-restarts without maintenance record
- pause/restart only through maintenance mode
- blocker logging for permissions, locked files, stale proof, or missing outputs

## Protected Boundary

This plan does not approve:

- Task Scheduler changes
- runtime pause or restart
- process kill
- worker restart
- script implementation
- deletion
- Amazon/security
- prices, Sheets, databases, purchases, receiving, or send-to-Amazon

## Expected Outcome

SellerOne should end up with:

- a clear script health register
- a reviewed Task Scheduler map
- a recommendation for what stays, what changes, and what retires
- a future monitoring design that fits SellerOne 2.1

## Stop Condition

Stop before changing Task Scheduler, runtime, scripts, data, outputs, automations, or business systems.
