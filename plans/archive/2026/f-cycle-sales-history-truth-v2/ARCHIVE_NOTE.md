# Archive Note

## Status
- Archived on 2026-04-20.

## Why this plan was archived
- The F sales-history truth build reached its implementation target inside this plan:
  - trusted completed-month demand basis
  - price-qualified demand
  - maturity, seasonality, stability, and recent-performance states
  - explicit `pass` / `fail` / `manual_review` output with confidence
  - one-off operator accuracy pack
  - one-off post-purchase learning pack
- The remaining gaps are not unresolved code inside this plan.
- The remaining gaps are operator evidence fill and optional future recalibration.

## What this archive preserves
- The full business-first F decision-model planning spine.
- Batch-by-batch proof from demand-truth hardening through learning-pack closeout.
- Runbook and data contracts for:
  - decision output
  - operator validation
  - post-purchase learning

## Work carried forward
- No direct active successor plan is required at archive time.
- Start the next F active ticket only when one of these becomes true:
  - operator sold-30d checks are filled and calibration review is requested
  - learning actuals are filled and recalibration is requested
  - targeted coverage cleanup is explicitly approved as a separate root-cause ticket

## Evidence at archive time
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md` records:
  - all seven batches complete
  - F-scoped build-lane health checks `ok`
  - accuracy pack proof complete
  - learning pack proof complete
- latest proof counts:
  - `F074`: rows `21` (`ok=21`, `warn=0`, `fail=0`)
  - `f_sales_history_accuracy_pack_latest.csv`: rows `18`
  - `f_sales_history_learning_review_latest.csv`: rows `266`

## Known unresolved state at archive time
- Coverage is still incomplete, but it is not a blocker for the delivered decision model:
  - latest successful ASIN captures: `2342`
  - latest failed ASIN captures: `2214`
  - targeted retry subset rows: `2207`
- Operator sold-30d checks are still unfilled.
- Post-purchase actual outcome checkpoints are still unfilled.
