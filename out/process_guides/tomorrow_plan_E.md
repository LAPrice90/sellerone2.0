# Tomorrow Plan - E Cycle (Decision Layer)

## Purpose
- Turn E-Research into a concrete plan for E cycle improvements without changing daily loops today.
- Keep this as an execution checklist for tomorrow morning.

## Inputs and references
- reference/E-Research.txt
- out/process_guides/e_cycle_runbook.md
- out/process_guides/e_cycle_phases.md
- out/process_guides/e_cycle_checklist.md
- out/process_guides/todo_list.md

## Morning checklist (before any changes)
- Run A015 to see current FAIL/WARN and capture the snapshot path.
- Confirm E outputs exist from last run:
  - out/sku_sales_velocity.csv
  - out/sku_roi_snapshot.csv
  - out/sku_restock_signals.csv
  - out/sku_performance_summary.csv
- Confirm foreign ROI outputs exist:
  - out/sku_roi_snapshot_uk.csv
  - out/sku_roi_snapshot_non_uk.csv
  - out/sku_roi_snapshot_by_country.csv

## Plan steps (execution order)
1) Velocity model update plan
   - Define windows: 7, 30, 90 days (and 180 for seasonal SKUs).
   - Define blending rule: weighted average with recent bias.
   - Define stockout handling: exclude zero-in-stock days from velocity.
   - Decide outlier rule: trimmed mean or spike exclusion list.

2) Buy box and price suppression handling plan
   - Decide detection rule for suppressed periods (example: low sales + high BSR).
   - Decide adjustment rule: replace suppressed days with expected sales.
   - Identify required data sources (BSR signals, buy box %, competitor stock if available).
   - If data is missing, mark this as "phase 2" and do not block phase 1.

3) Long out-of-stock (OOS) recovery plan
   - Define threshold for "long OOS" (example: 30+ days).
   - Define ramp-up model:
     - week 1-2: 50% of old velocity
     - week 3-4: 70%
     - week 5+: 100% if confirmed by actual sales
   - Add a note: use category or competitor proxy if old data is stale.

4) Decision logging and overrides plan
   - Add per-SKU reasoning fields to E outputs:
     - velocity_window_used
     - stockout_days_excluded
     - outlier_adjustment_flag
     - override_flag (if manual override applied)
   - Create a minimal "override" file format for manual inputs (local CSV).
   - Log overrides with reason and timestamp.

5) Decision layer (Script E) outputs plan
   - Ensure outputs are:
     - Restock signals with confidence + reason
     - KPI summary per SKU: velocity, ROI, margin, days of cover
   - Add optional flags:
     - "needs_review" when data confidence is low
     - "foreign_only_sales" when sales are non-UK only

6) Validation plan
   - Run E cycle locally and confirm:
     - No FAIL in A015
     - ROI and velocity files updated
     - New columns present in E outputs
   - Spot check 3 SKUs across UK and non-UK for sanity.

## Open questions to answer tomorrow
- What data is available to detect buy box suppression reliably?
- Do we want a separate velocity model per country or blended?
- Should overrides be per-SKU or per-ASIN?

## Constraints
- Do not change sheets unless explicitly asked.
- Do not use one-off scripts in daily loops.
- Root cause changes only, no downstream masking.

