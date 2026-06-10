# SO21 Rep Briefing Pilot

Created: 2026-06-08

## Decision

Luke approved creating the first SellerOne 2.1 pilot automation as a paused shell.

## Automation

- Automation id: `so21-rep-briefing`
- Display name: `SO21-REP-BRIEFING`
- Status: `PAUSED`
- Proposed cadence: every 12 hours if later activated
- Activation status: not activated

## Verification

- First inventory after creation showed the pilot as active, which was not the approved state.
- The automation was immediately updated back to `PAUSED`.
- Follow-up inventory at 2026-06-08T14:02Z showed Codex automations found: 20, active: 0, paused: 20.
- Windows scheduled tasks still ready after pause: 0.

## Purpose

Read the SellerOne 2.1 control files and produce a short plain-English Rep briefing only when there is a real decision, material state change, new or worse failure, or Monday-readiness change.

## Allowed

- read current control evidence
- summarize current phase
- summarize queue state
- summarize blocked work
- summarize health state
- summarize automation state
- identify the recommended next task

## Forbidden

- no worker runs
- no price changes
- no queue edits
- no Google Sheets writes
- no Product DB or local DB alignment
- no output deletion
- no scheduler restart or re-enable
- no Amazon login or security action
- no business decisions

## Next Gate

The next decision is whether to activate this paused pilot for its first scheduled briefing run.
