# SO21 Scheduler And H Staged Execution Plan

Created: 2026-06-09
Status: planning

## Plain-English Purpose

This plan turns the two next practical recommendations into a safe order of work:

- review Windows Task Scheduler against the new SellerOne 2.1 style
- design a dry-run route for the large H staged storage area

Both jobs are review/design only. They do not approve deletion, scheduler edits, runtime pause/restart, H runs, price changes, or business actions.

## Why These Two First

### Task Scheduler Review

SellerOne still has Windows scheduled tasks that may belong to different worlds:

- business runtime
- control-desk reporting
- old one-off probes
- legacy manager noise
- maintenance protected items

The new system needs a clear answer: which tasks fit the new model, which need redesign, and which should stay protected.

### H Staged Dry-Run Design

The morning report measured H staged data as the largest storage opportunity.

This does not mean it is trash. It means it needs a careful owner-proof and dry-run manifest route before any cleanup is proposed.

## Recommended Sequence

### Step 1 - Task Scheduler New-Style Review

Job: `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW`

Goal:

- classify every visible SellerOne-related scheduled task against the new 2.1 style

Output:

- a review report under `CONTROL/`

Must answer:

- Business Runtime?
- Control Desk Automation?
- Maintenance Protected?
- Retire or legacy candidate?
- Needs rewrite into a 2.1 control automation?
- Needs Luke decision?

Forbidden:

- no Task Scheduler changes
- no runtime pause or restart
- no process kill
- no worker restart
- no Amazon/security
- no prices, Sheets, databases, purchases, receiving, or send-to-Amazon

### Step 2 - H Staged Retention Dry-Run Design

Job: `SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN`

Goal:

- design how to safely measure and classify H staged data before any cleanup proposal

Output:

- a design report under `CONTROL/`

Must answer:

- what H staged folders exist
- which data looks current proof
- which data looks failed partial
- which data looks historical audit
- which data looks duplicate or repeated
- which data must remain protected
- what exact dry-run manifest would be needed before cleanup
- what graphs should be shown to Luke before any approval

Forbidden:

- no deletion
- no movement
- no compression
- no purge
- no archive apply
- no H run
- no scheduler change
- no price change
- no database, Sheet, queue, Amazon, purchase, receiving, or send-to-Amazon action

### Step 3 - Proposal Report For Luke

After both reports exist, create a short customer-style proposal:

- what the scheduler review found
- what H staged data likely offers
- what risk remains
- recommended next action
- graphs where measured data exists
- approve / hold / reject decision box

## Success Criteria

This plan is successful when:

- Scheduler tasks are classified into the new style.
- H staged cleanup has a dry-run design, not a blind cleanup.
- Luke gets a decision-ready proposal before any state-changing action.
- No protected business action occurs.

## Current Recommendation

Start with `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW`, then `SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN`.
