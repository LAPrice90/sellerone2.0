# SellerOne Manager Failure Report And Reset Brief - 2026-06-12

## Purpose

This report is a plain-English base document for starting fresh communication without dragging the full noisy chat history forward.

This current management pilot should be treated as a failed first build, not as a trusted operating system.

It produced useful parts, but it did not reliably protect Luke from missing obvious business problems.

## Executive Verdict

The current SellerOne Manager system is not yet trustworthy enough to run as Luke's autonomous management layer.

It can:

- create task packets
- create reports
- update a board
- dispatch workers
- read some evidence
- keep some follow-up structure

But it failed the core business test:

- it did not reliably spot urgent risk before Luke did
- it did not keep money-risk work above cosmetic work
- it confused "blocked safely" with "business risk solved"
- it let warning evidence sit inside technical files without becoming a loud manager action

The clearest example is `A2-T2AC-TW3L`.

The system had warning evidence that the repricer floor path was not clean. It knew H was blocking the write because of a token-selection conflict. But the task board still parked Token Pricing Issue as if the guard being active meant the business risk was handled.

That was wrong.

## How The System Works Now

### 1. Rep Chat

This chat is meant to be Luke's front desk.

Its job should be:

- speak plainly
- turn ideas into jobs
- explain business status
- protect Luke from worker noise
- escalate real decisions
- avoid raw technical output unless Luke asks

What went wrong:

- the Rep chat became too involved in manual correction
- it kept translating after the fact instead of proving the system was catching issues itself
- it sometimes sounded like it was handing Luke work instead of managing work

### 2. Boardroom Task List

The board is the simple HTML list Luke can look at.

Its job should be:

- show the big open areas
- show what is being worked
- show what is blocked
- show what needs proof
- keep urgent business risk visible

What went wrong:

- the board became a presentation layer, not a truth layer
- statuses were too vague
- jobs sat in the wrong section
- "ready later" was used for an unresolved pricing risk
- manual fixes made it look better without proving the manager would catch the next issue

Current rule:

The board is only a checklist until it is generated from stronger evidence.

### 3. Foreman / Shift Manager

The Foreman is meant to be the working manager.

Its job should be:

- check the queue
- check workers
- detect finished jobs
- detect stuck jobs
- dispatch safe approved work
- close each job into a real outcome

What went wrong:

- it was too report-driven
- it could notice result files but still miss the wider business objective
- it needed repeated correction from Luke and Rep chat
- it did not reliably turn warnings into action
- it did not clearly prove that idle time was being managed

Current status:

The Foreman is now better than it was, but it is still in pilot. It should not be treated as fully autonomous.

### 4. Worker Packets

Worker packets define bounded jobs.

Their job should be:

- give one worker a clear task
- define allowed actions
- define forbidden actions
- define the proof file required

What went wrong:

- too many packets were created without a strong business-risk order
- reports were sometimes treated as progress even when the original risk remained open
- worker completion was not always tied back to "did the business problem improve?"

### 5. MOT / Health Checks

MOT is meant to inspect system health.

Its job should be:

- find failures
- classify risk
- tell the manager what matters
- create follow-up work when needed

What went wrong:

- MOT warnings were too technical
- warnings did not always become active board items
- warning severity did not match business severity
- Luke found problems by looking at the business, not because MOT forced attention

This is the biggest structural failure.

### 6. Business Runtime

Business Runtime means the real SellerOne cycles that run the business.

Examples:

- repricing
- H cycle
- F scanner
- order and stock cycles
- restocking inputs

This must stay separate from Control Desk Automations.

What went wrong:

- discussions about pausing, workers, schedulers, and control jobs became mixed together
- Luke lost confidence that business runtime was being protected
- the management system sometimes talked like control-layer cleanup and business operation were the same thing

Current rule:

Business Runtime must never be disabled or changed without explicit approval and evidence.

## Current Known Issues

### 1. Pricing And Floor Risk

This is the biggest current risk.

The pricing/floor audit found:

- 4 red pricing/floor risk SKUs
- 18 amber watch SKUs

Red SKUs:

- `A2-T2AC-TW3L`
- `CN-NR50-TSFE`
- `LV-425G-BY4X`
- `6V-EEC1-2S9Z`

Known problem:

- fresh receipt tokens can exist
- H can still select older fallback tokens
- H may block the floor
- repricer may not write
- the manager may not shout loudly enough

Recent improvement:

- the H token-selection repair worker has completed at code/test level
- next proof still needs current H output evidence

Unresolved:

- the four red SKUs are not closed until fresh H proof confirms the behavior in current outputs

### 2. MOT Does Not Escalate Hard Enough

The system can contain warning evidence and still fail to present it as urgent.

That is why Luke found the A2 issue manually.

Required fix:

- MOT warnings that affect money or runtime must automatically become active board risks
- warnings must say the business meaning, not only the technical state

### 3. Worker Completion Is Not Proof

A worker result file does not mean the job is done.

The real closure test must be:

- did the business risk reduce?
- is the live/runtime proof current?
- is a protected decision still needed?
- is the next packet created if not solved?

The system has been too willing to treat "report exists" as progress.

### 4. Too Many Sources Of Truth

Current sources include:

- control files
- task packets
- result reports
- MOT outputs
- Foreman status
- board HTML
- chat history
- old plans
- old work logs

This creates drift.

The system needs one simple operating view:

- business risks
- active work
- blocked decisions
- proof waiting
- completed with proof

Everything else should be evidence, not command.

### 5. The Board Is Not Strong Enough Yet

The board is useful visually, but it is not yet trustworthy.

It should not be manually maintained as the source of truth.

It should be generated from:

- risk register
- current packets
- proof status
- Foreman closure state

Until then, the board can mislead.

### 6. Automation Is Still Fragile

The Foreman heartbeat can run, but the operating loop is not proven.

The loop still depends too much on:

- prompts
- manual corrections
- chat interpretation
- loosely connected files

It needs harder rules:

- no silent idle when safe work exists
- no "done" without proof
- no parked status for unresolved money risk
- no broad dispatch without priority
- no worker result closed without business meaning

## Why Simple Issues Were Missed

The short answer:

The system was checking activity, not business truth.

It asked:

- did a worker finish?
- does a report exist?
- did a guard block the unsafe action?
- does the board have a status?

It did not consistently ask:

- are we still losing money?
- is the floor actually current?
- did repricing actually receive the right floor?
- did this warning become a manager action?
- is Luke still exposed?

That is why Luke found issues by accident.

The system had signals, but no reliable business-risk escalation layer.

## What Should Be Kept

Useful parts to carry into the fresh communication:

- the role split: Rep chat, Foreman, Workers, Reviewers
- approved task packets
- protected action boundaries
- separation of Business Runtime and Control Desk Automations
- pricing/floor audit result
- trust-reset report
- Foreman proof-closure concept
- simple board idea, but only as a view
- worker packets with forbidden actions

## What Should Not Be Carried Forward As Truth

Do not trust these as final operating truth:

- old chat promises
- old board placement
- old "done" wording
- old work logs
- old manager reports that do not prove business outcome
- any task status that is not tied to proof
- broad claims that the system is autonomous

## Recommended Fresh Communication Setup

Start a fresh management communication using only a short base pack.

The fresh chat should read:

1. `CONTROL/SELLERONE_MANAGER_FAILURE_REPORT_AND_RESET_BRIEF_20260612.md`
2. `CONTROL/SYSTEM_TRUST_RESET_AND_BLINDSPOT_AUDIT_20260612.md`
3. `CONTROL/BUSINESS_RISK_AUDIT_PRICING_FLOORS_V1_RESULT_20260612.md`
4. `CONTROL/FOREMAN_LIVE_PILOT_STATUS.md`
5. `CONTROL/SO21_FOREMAN_PILOT_ACTIVATION_20260611.md`

The fresh chat should not read the full old conversation unless specifically needed.

## New Operating Rule

The manager must start each check with business risks, not task lists.

Daily order:

1. pricing and floor safety
2. runtime alive and progressing
3. finished scans reaching review
4. restocking data freshness
5. worker results waiting closure
6. feature work

## What Success Looks Like

The rebuilt system is working only when:

- Luke hears about money-risk before he spots it manually
- red risks stay visible until proof clears them
- worker completion is not confused with business completion
- MOT warnings automatically become action when they matter
- the board is generated from evidence, not manually tidied
- Foreman can explain what moved, what is blocked, and what proof is due

## Final Position

This management pilot should be called a failed first version.

Not because every part is useless, but because the trust layer failed.

The right move is to preserve the useful evidence, stop treating this thread as clean operating memory, and start a fresh communication from this reset brief.

