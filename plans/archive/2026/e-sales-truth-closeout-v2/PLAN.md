# E Sales Truth Closeout v2

## Purpose

Close the remaining operator-facing gaps after the core B/E sales-truth recovery work.

This is not a new root-cause investigation. The core math is mostly corrected. The remaining work is to make the corrected truth visible, publishable, and self-checking.

## Plain-English Summary

The last round fixed the main truth tables, but one report that people actually read is still out of line with the corrected outputs.

That means the system is in an awkward state:

1. raw truth is better
2. reconciliation is better
3. operator-facing report is not fully caught up
4. publish path is not fully caught up
5. automated health does not yet guard that gap

## Review Outcome

Confirmed good:

1. performance summary units now align to ROI truth
2. reconciliation mismatch rows are `0`
3. daily truth output exists with explicit finalized/provisional state
4. provisional `A2-T2AC-TW3L` data currently shows `6` distinct orders, not `5`

Confirmed remaining issues:

1. `e_study_report.csv` is stale/misaligned
2. proof pack skipped `E005`
3. publish path does not include the new truth outputs
4. no freshness/alignment guard exists for the operator report
5. live-loop verification is still pending

## Delivery Goal

Finish the closeout so the E flow is not only correct in raw CSVs, but also correct in the report layer, the publish layer, and the health layer.

## Phase Map

### Phase 1 - Repair the operator report

Update `E005_build_study_report.py` so the study report is rebuilt from the corrected performance summary and explicitly surfaces:

- truth units
- velocity units
- unit source
- latest daily sales-truth state

### Phase 2 - Extend the publish contract

Update the E publish script so the operator-facing truth outputs are available in the publish path when sheet writing is enabled.

### Phase 3 - Add stale-output and alignment guards

Add health/test coverage that fails if the study report is older than upstream truth or if its key economics no longer match the performance summary.

### Phase 4 - Prove using the real E cycle order

Run the full E build path in the real order:

- `E001`
- `E002`
- `E003`
- `E004`
- `E005`
- `E006`
- `E007`

Then confirm the operator report and truth outputs agree.

### Phase 5 - Live verification closeout

Use the next scheduled cycle proof window to confirm the post-change health snapshot after the implementation timestamp.

## Ready-When Definition

This plan is complete only when:

1. the study report is aligned and fresh
2. the publish contract includes the corrected truth outputs
3. health checks would catch the stale-report problem automatically
4. the real E cycle order has been proved in isolation
5. live verification has moved from pending to confirmed

## Current Status

Execution complete for this plan.

What was achieved:

1. `E005` now rebuilds the operator report from corrected truth and surfaces latest daily truth
2. `E010` now includes the new operator/truth outputs in the publish contract
3. A015 now fails on stale study-report output and study-report truth misalignment
4. a real post-change E cycle completed successfully with fresh E health at `0` fail / `0` warn

Residual scope outside this ticket:

1. global health remains stale because global `A015` was not rerun here
2. unrelated H-side alerts remain open in the stale global snapshot
