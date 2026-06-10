# SO21 Rep Briefing Activation

Created: 2026-06-08

## Decision

Luke approved activating the paused `SO21-REP-BRIEFING` pilot.

## Activated Automation

- Automation id: `so21-rep-briefing`
- Display name: `SO21-REP-BRIEFING`
- Status after activation: `ACTIVE`
- Scope: Rep briefing only
- First-run proof status: pending first scheduled run

## Boundary

The active pilot may read SellerOne 2.1 control files and produce a short Rep briefing. It must not run workers, change prices, edit queues, write Sheets, align databases, delete outputs, restart schedulers, touch Amazon login/security, or make business decisions.

## Success Condition

The pilot is proven when its first scheduled briefing produces a plain-English control summary without protected actions, duplicate manager chatter, or old-cycle heartbeat behavior.

## Failure Path

If the first run is noisy, tries to act outside the Rep briefing scope, or produces stale/confusing state, pause `so21-rep-briefing` immediately and revise the prompt before another activation attempt.
