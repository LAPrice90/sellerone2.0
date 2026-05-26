# E Analytics Todo

Created: 2026-05-26
Owner flow: E
Business purpose: ROI, velocity, break-even, and performance truth for restock and pricing.

## Source Plans To Read First

- `project_control/EXPECTATIONS/E_cycle_expectations.md`
- `plans/active/o-net-fee-restock-bridge-2026-05-19/CODING_PLAN.md`
- `project_control/TASK_QUEUE.md`

## Current Evidence

- `out/cycle_alerts/summary.csv` shows E has 0 FAIL and 0 WARN.
- O net-fee bridge uses E output to stop gross-profit shortcuts from creating bad buy recommendations.
- H health currently warns that the chosen E output as-of is not in the expected date set, so date interpretation should be checked before relying on H-facing E freshness warnings.

## Plain-English Finish Line

E is endgame-ready when O restocking can trust net ROI, velocity, break-even price, refund drag, and fee drag.

## Phase 0 - Keep E Scoped Proof Separate

- [ ] Use E-scoped evidence for E health, not global H warnings alone.
- [ ] Confirm latest E run log success and output row counts when needed.
- [ ] Keep O net-fee bridge monitoring active until its review window closes.

Success condition:
- E remains 0 FAIL / 0 WARN in its scoped checklist.

## Phase 1 - Support Restock Buying Decisions

- [ ] Confirm O source rows carry E net-fee fields.
- [ ] Confirm action-ready O rows require fresh net-fee truth.
- [ ] Confirm net ROI and gross ROI are both visible where needed but net ROI controls buy readiness.

Success condition:
- Restock recommendations do not look profitable just because Amazon fee drag was left out.

## Stop Conditions

Stop before changing anything if:

- E proof would be judged from another flow's stale output
- O buy readiness would be patched downstream instead of fixing E/O source calculations

