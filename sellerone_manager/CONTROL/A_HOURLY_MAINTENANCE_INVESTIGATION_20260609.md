# A Hourly Maintenance Investigation

Created: 2026-06-09 18:05 UK
Owner: Rep / Operations
Mode: read-only investigation

## Plain-English Finding

Luke's concern is valid.

`AMZ Pricing Summary Hourly` is not a small hourly summary job. It launches the same full A runner as the normal morning A task.

That means an hourly task is activating a sequence that behaves like the morning A cycle.

## What Was Checked

Read-only checks only:

- Windows Task Scheduler entry for `AMZ Pricing Summary`
- Windows Task Scheduler entry for `AMZ Pricing Summary Hourly`
- A launcher batch file
- A runner maintenance handoff logic
- current maintenance lock files
- current A process list
- recent A manifests and handoff proof history

No scheduler state, runtime process, price, Sheet, database, output, Amazon, or queue state was changed by this investigation.

## Scheduler Finding

Daily A task:

- name: `AMZ Pricing Summary`
- schedule: daily at 06:00
- action: `run_A_all.bat`
- current classification: expected morning A runtime

Hourly A task:

- name: `AMZ Pricing Summary Hourly`
- schedule: every 1 hour from 12:52
- action: `run_A_all.bat`
- current classification: business runtime, but suspect design mismatch

The hourly task uses the short path `C:\Users\Luke\Desktop\SELLER~1.0`, which resolves to `SellerOne 2.0`.

So the hourly task is not running a separate old copy. It is running the live SellerOne 2.0 A launcher.

## Maintenance Mode Finding

`run_A_all.py` always starts by requesting A maintenance handoff from B.

The flow is:

1. write `maintenance.requested`
2. wait for B to report ready or not running
3. write `maintenance.active`
4. run the A sequence
5. clear maintenance markers
6. write A handoff proof

This is sensible for the morning full A run.

It is risky when fired hourly because it repeatedly asks the runtime to make room for A.

## Current Live Finding

At the time of investigation:

- `AMZ Pricing Summary Hourly` was disabled for future starts
- but the already-started 17:52 instance was still running
- A process PID `35868` was running `run_A_all.py`
- child process PID `9604` was running A002 catalog work
- maintenance markers were A-owned

Plain English: disabling the task stops future launches, but it does not automatically stop the A run that already started.

## Evidence From Today

Recent A runs show repeated hourly full-cycle behaviour.

Examples from 2026-06-09:

- 00:53 UTC partial
- 01:52 UTC partial
- 02:52 UTC partial
- 03:52 UTC partial
- 04:52 UTC partial
- 05:53 UTC completed
- 07:53 UTC partial
- 08:52 UTC partial
- 09:55 UTC partial
- 10:52 UTC completed
- 11:59 UTC partial
- 12:54 UTC completed
- 13:52 UTC completed
- 14:53 UTC partial
- 15:52 UTC completed
- 16:52 UTC currently running during this investigation

This is not a single morning A cycle.

## Business Risk

The hourly A task can:

- take the shared maintenance gate during the day
- block F owner handoff and proof windows
- interrupt or delay other runtime maintenance work
- repeatedly run heavy Amazon/API/data refresh work
- create partial A runs that look like health problems
- make Operations think the business is blocked by A when the real issue is scheduler design

## Initial Verdict

The hourly A task should not be treated as harmless until reviewed.

It may have been created to refresh useful A outputs during the day, but it is using the full morning A runner to do that.

That is too broad for hourly use while F is under emergency repair.

## Recommendation

For tonight:

- keep F as the emergency lane
- keep `AMZ Pricing Summary Hourly` held when it blocks F
- do not touch the normal daily `AMZ Pricing Summary` 06:00 task
- do not permanently delete or redesign the hourly task during the F emergency

For the next proper fix:

- create a bounded A scheduler review/repair packet
- decide whether hourly A is needed at all
- if hourly refresh is needed, split it into a lightweight hourly job that does not run the full morning A cycle
- keep full `run_A_all.bat` for the daily morning task only unless Luke approves otherwise

## Suggested Worker Packet

Job ref:

- `A-HOURLY-MAINTENANCE-ROLE-REVIEW`

Purpose:

- classify whether `AMZ Pricing Summary Hourly` is needed
- identify which A outputs, if any, truly need hourly refresh
- design a safe lightweight hourly alternative if needed
- confirm how A should use maintenance mode without blocking F and other cycles

Boundaries:

- read-only first
- no scheduler deletion
- no permanent disable/enable decision without Luke approval
- no price, Sheet, database, output deletion, order, receiving, send-to-Amazon, or Amazon security action
