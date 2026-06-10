# FINAL PASS CRITERIA

The ticket is over the line only when every item below is true.

## Phase Completion

1. Phase 0 completed with a frozen input manifest
2. Phase 1 completed with corrected `E004`
3. Phase 2 completed with new daily sales-truth output
4. Phase 3 completed with E-flow wiring
5. Phase 4 completed with targeted health-gate coverage
6. Phase 5 completed with repeatable frozen-input proof
7. Phase 6 completed with correct final status language

## Data Truth Gates

1. `out/sales_truth_reconciliation_latest.csv` has `0` mismatch rows
2. `out/sku_performance_summary.csv` no longer presents mixed unit/money truth as one number set
3. For rows where `units_sold_roi > 0`, `units_sold` equals `units_sold_roi`
4. `out/sku_daily_sales_truth_latest.csv` exists and labels rows as:
   - `finalized_ledger`
   - `provisional_order_master`
5. No operator-facing output silently treats provisional data as finalized truth

## Sample Proof Gates

For `A2-T2AC-TW3L`:

1. finalized row exists for `2026-04-16` with:
   - units `3`
   - revenue `27.24`
   - profit `1.86`
2. provisional row exists for `2026-04-17` with:
   - units `6`
   - revenue `55.92`
   - profit `4.98`
3. Sellerboard `10.87` is documented as comparison-only, not adopted as truth

## Test Gates

1. `py_compile` passes for all changed flow files and related tests
2. All targeted E-flow tests pass
3. Targeted A015 helper tests pass
4. Two consecutive isolated rebuilds against the same frozen inputs produce the same result

## Runtime Status Gate

The ticket may be classified as ready for sign-off only with this wording:

- `code fix applied`
- `isolated verification passed`
- `live loop verification pending next cycle check`

It must not be described as fully proven live until a later scheduled cycle confirms post-change health after the implementation timestamp.

## Final Decision Rule

If any one item above is missing, the ticket is not ready to sign off.
