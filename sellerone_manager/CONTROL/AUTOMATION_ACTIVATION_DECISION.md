# Automation Activation Decision

Date: 2026-06-08

## Decision

Activate the first SellerOne 2.1 automation pilot: `SO21-REP-BRIEFING`.

## Scope

This decision applies only to `SO21-REP-BRIEFING`.

It does not approve:

- activating `SO21-HEALTH-WATCHER`
- activating `SO21-STORAGE-CUSTODIAN`
- activating `SO21-USAGE-REPORTER`
- creating or activating `SO21-REVIEW-WATCHER`
- re-enabling old Codex automations
- re-enabling Windows scheduled tasks
- running workers
- changing prices, queues, Sheets, databases, outputs, or Amazon login/security

## Proof Needed

The remaining proof is the first scheduled Rep briefing run. The run must stay inside the Rep boundary and produce a useful plain-English control summary.
