# REVIEW FINDINGS

## Scope Reviewed

Reviewed after the `b-e-sales-truth-recovery-v1` coding pass:

- `out/sku_roi_snapshot.csv`
- `out/sku_performance_summary.csv`
- `out/e_study_report.csv`
- `out/sku_daily_sales_truth_latest.csv`
- `out/sales_truth_reconciliation_latest.csv`
- `scripts/flows/E/E005_build_study_report.py`
- `scripts/flows/E/E010_publish_e_outputs.py`
- `scripts/cycles/run_E_cycle.py`
- `scripts/flows/A/A015_build_system_health_check.py`

## What Looks Correct

1. `sku_performance_summary.csv` no longer mixes ROI unit truth and velocity unit truth.
2. `sales_truth_reconciliation_latest.csv` currently has `0` mismatch rows.
3. `sku_daily_sales_truth_latest.csv` has explicit finalized vs provisional states.
4. Current provisional rows look structurally clean:
   - provisional rows = `9`
   - today's duplicate `Order ID + SKU` groups = `0`
   - provisional rows with missing FX = `0`

## What Looks Off

### Finding 1 - `e_study_report.csv` is stale relative to corrected upstream truth

Evidence:

- `out/sku_performance_summary.csv` mtime: `2026-04-17T21:57:50Z`
- `out/e_study_report.csv` mtime: `2026-04-17T21:07:49Z`

Example SKU `0G-JB6S-PN34`:

- performance summary:
  - units_sold = `6.0`
  - revenue_exvat_gbp = `29.51`
  - profit_exvat_gbp = `-6.02`
- study report:
  - units_sold_30d = `6.0`
  - revenue_exvat_gbp_30d = `0.0`
  - profit_exvat_gbp_30d = `0.0`

This means the operator-facing report is not currently safe to trust.

### Finding 2 - the proof pack missed one downstream artifact

The isolated proof rebuilt:

- `E002`
- `E004`
- `E006`
- `E007`

But it did not rebuild `E005`, even though `run_E_cycle.py` includes `E005` in the normal sequence.

That left the operator report outside the proof window.

### Finding 3 - publish path is incomplete for the new truth outputs

`E010_publish_e_outputs.py` currently publishes only:

- sales velocity
- ROI snapshot
- restock signals
- performance summary

It does not publish:

- `e_study_report.csv`
- `sales_truth_reconciliation_latest.csv`
- `sku_daily_sales_truth_latest.csv`

So even after the new truth work, the operator-facing publish contract is incomplete.

### Finding 4 - there is no guard that would have caught Finding 1 automatically

`A015_build_system_health_check.py` now checks:

- performance-summary unit alignment
- daily-sales-truth schema/state

But it does not yet check:

1. whether `e_study_report.csv` is older than `sku_performance_summary.csv`
2. whether study-report truth fields match performance-summary truth fields

### Finding 5 - current local data for `A2-T2AC-TW3L` does not support the earlier `5`-sale assumption

Current `order_master.csv` review for `2026-04-17` shows:

- `6` rows
- `6` distinct order IDs
- provisional revenue = `55.92`
- provisional profit = `4.98`

So the current local data does not look like a duplicate-row bug for that SKU.

## Conclusion

The core truth layer is mostly in place.

The remaining work is now operator closeout work:

1. align the study report
2. extend publish outputs
3. add freshness/alignment guards
4. rerun proof using the real E cycle order
5. wait for live verification

## Resolution

This review set has now been worked through.

Resolved in execution:

1. study report stale/misaligned issue
2. publish contract gap
3. missing stale-report health guard
4. missing truth-alignment health guard
5. missing real-cycle proof for `E005`

Confirmed final E-flow state:

1. `checklist_E_split.csv` is fresh and clean after the real post-change cycle
2. `e_study_report.csv` is fresh relative to `sku_performance_summary.csv`
3. sample SKUs now match between report and truth layers
