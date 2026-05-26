# A Cycle Todo

Created: 2026-05-26
Owner flow: A
Business purpose: daily product, inventory, and health gate foundation.

## Source Plans To Read First

- `project_control/EXPECTATIONS/A_cycle_expectations.md`
- `project_control/MORNING_MOT_CHECKLIST.md`
- `project_control/TASK_QUEUE.md`
- A active plans under `plans/active/`

## Current Evidence

- `out/cycle_alerts/summary.csv` shows A has 0 FAIL and 1 WARN.
- Current A warning: stock receipts collection was skipped by guardrail due duplicate batch IDs.
- Duplicate batch evidence file: `out/stock_receipt_duplicate_batches.csv`.
- The duplicate rows shown are already `APPLIED` and reported as `idempotent_existing_order_key`.

## Plain-English Finish Line

A is endgame-ready when daily health can be trusted and it does not create false blockers for restock, pricing, or Product DB work.

## Phase 0 - Classify Current A Warning

- [ ] Review duplicate stock receipt batch evidence.
- [ ] Decide whether this is harmless idempotent history, user cleanup, or a real source-data issue.
- [ ] Do not run A015 ad hoc unless explicitly approved.
- [ ] Use owner-cycle evidence or an approved A-owned proof window.

Success condition:
- A warning is either fixed or recorded as a non-blocking exception with exact reason.

## Phase 1 - Keep A As Restock Foundation

- [ ] Confirm A inventory data freshness supports O restock.
- [ ] Confirm product and stock outputs needed by O have schema checks.
- [ ] Confirm A health gate continues to block unsafe publish paths.

Success condition:
- O can trust A stock/inventory truth for reorder calculations.

## Stop Conditions

Stop before changing anything if:

- the next action would write Google Sheets
- the next action is only an ad-hoc A015 run
- duplicate batch root cause is unclear and data would be changed

