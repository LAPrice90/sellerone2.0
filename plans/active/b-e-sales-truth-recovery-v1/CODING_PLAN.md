# CODING PLAN

## Ticket

B/E sales-truth recovery to full sign-off readiness.

## Objective

Finish the remaining coding and proof work so SKU sales and profit reporting are internally aligned, operator-readable, and ready for final runtime confirmation.

## Execution Rule

This plan must be executable by Codex without needing new business interpretation.

The remaining work must follow:

1. phase
2. scoped test
3. written proof
4. next phase

No later phase may begin until the prior phase proof is written.

## Frozen-Input Rule

Before Phase 1 starts, Codex must create a frozen manifest for these files and then treat them as fixed inputs for the rest of the ticket:

- `out/order_ledger_fx.csv`
- `out/order_master.csv`
- `out/fx_rates_daily.csv`
- `out/sku_sales_velocity.csv`
- `out/sku_roi_snapshot.csv`
- `out/sku_performance_summary.csv`
- `out/sales_truth_sku_30d_latest.csv`
- `out/sales_truth_reconciliation_latest.csv`

The frozen manifest must record:

- absolute path
- modified time
- file size
- hash

If any frozen input changes during execution, stop and record that the proof window was broken.

## Fixed Interpretation Rules

These rules are not up for re-debate during execution:

1. Finalized truth comes from `order_ledger_fx`
2. Provisional same-day truth comes from `order_master`
3. Sellerboard is comparison-only when fee values are incomplete
4. Revenue/profit and units must never be presented as one truth if they came from different source layers

## Phase Ownership

### Phase 0 - Freeze baseline

Status: Complete

Allowed files:

- `plans/active/b-e-sales-truth-recovery-v1/FROZEN_INPUT_MANIFEST.md`
- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`

Actions:

1. Record the frozen manifest for all required inputs.
2. Record the current known proof anchors:
   - `sales_truth_reconciliation_latest.csv` mismatch rows = `0`
   - `sku_roi_snapshot.csv` revenue/profit truth is now ledger-led
   - `sku_performance_summary.csv` still has unit-count misalignment
   - `A2-T2AC-TW3L` finalized/provisional split is not yet explicitly published

Tests:

1. Check every frozen file exists.
2. Check every frozen file has hash and modified-time entry in the manifest.

Pass condition:

The frozen manifest exists and all later phases can point back to one stable baseline.

Automatic next step:

Start Phase 1.

### Phase 1 - Correct performance-summary unit truth

Status: Complete

Goal:

Stop `E004` from publishing a mixed truth where units come from velocity-side data but money comes from ROI/ledger truth.

Allowed files:

- `scripts/flows/E/E004_build_performance_summary.py`
- `tests/test_e004_build_performance_summary.py`
- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`

Required implementation result:

One of these must become true:

1. `units_sold` is aligned to finalized ROI truth whenever revenue/profit are ROI truth
2. or the file keeps separate fields, for example:
   - `units_sold_truth`
   - `velocity_units_sold_30d`

What is not allowed:

- keeping a single `units_sold` field that still comes from a different source than revenue/profit
- post-processing the output downstream to hide the mismatch

Scoped tests:

1. Add a fixture where velocity says `7` units and ROI truth says `5`
2. Assert the published economic unit field follows ROI truth
3. Assert any velocity-side count is clearly separated and labelled
4. Rebuild `E004`
5. Check sample SKU `A2-T2AC-TW3L`

Required proof:

1. `sku_performance_summary.csv` no longer mixes unit truth with money truth
2. `A2-T2AC-TW3L` shows aligned units for the economic truth layer

Pass condition:

For every row with ROI revenue/profit, the economic unit count is either aligned or explicitly separated.

Automatic next step:

Start Phase 2.

### Phase 2 - Create explicit daily sales-truth output

Status: Complete

Goal:

Create a daily output that tells the operator exactly what is finalized and what is provisional.

Allowed files:

- `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- `tests/test_e007_build_sku_daily_sales_truth.py`
- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`

Required output:

- `out/sku_daily_sales_truth_latest.csv`

Required columns:

- `sku`
- `date`
- `source_state`
- `units`
- `revenue_gbp`
- `profit_gbp`
- `fees_gbp`
- `cogs_gbp`
- `confidence_status`
- `notes`

Required source-state values:

- `finalized_ledger`
- `provisional_order_master`

Required confidence behavior:

1. Finalized ledger rows must be marked high confidence
2. Provisional order-master rows must be marked provisional
3. External Sellerboard-style values must not be published as truth

Scoped tests:

1. Build finalized-ledger-only case
2. Build provisional-only same-day case
3. Build mixed case for one SKU across two dates
4. Assert source-state labels are explicit
5. Assert sample SKU `A2-T2AC-TW3L` can be represented as:
   - finalized `2026-04-16`: `3` units, `1.86` profit
   - provisional `2026-04-17`: `5` units, `4.15` profit

Required proof:

The output exists and makes it impossible to confuse finalized and provisional sales truth.

Pass condition:

An operator can answer "what happened today?" without mixing finalized and provisional figures.

Automatic next step:

Start Phase 3.

### Phase 3 - Wire daily truth into the E flow

Status: Complete

Goal:

Make the new daily-truth output part of the normal E build so it is not a side tool.

Allowed files:

- `scripts/cycles/run_E_cycle.py`
- `tests/test_e_split_health_gate.py`
- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`

Required implementation result:

1. E flow task list includes `E007_build_sku_daily_sales_truth.py`
2. E flow artifact checks include `out/sku_daily_sales_truth_latest.csv`

Scoped tests:

1. Assert the task is in the E task list
2. Assert the artifact is in the E artifact expectations
3. Run the isolated E builders in order:
   - `E002`
   - `E004`
   - `E006`
   - `E007`

Required proof:

The new daily truth file is treated as a standard E artifact and rebuilds cleanly.

Pass condition:

A normal E run would generate the daily truth output without any special one-off step.

Automatic next step:

Start Phase 4.

### Phase 4 - Add health and regression gates

Status: Complete

Goal:

Make future regressions visible at the health/test layer.

Allowed files:

- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_a015_health_check_runtime.py`
- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`

Important rule:

Codex may edit A015 and run targeted tests, but must not run an ad-hoc A script unless the user explicitly asks.

Required checks:

1. performance-summary economic units align with ROI truth
2. daily sales-truth schema is valid
3. daily sales-truth state is explicit
4. provisional rows are not silently treated as finalized truth

Scoped tests:

1. Add helper-level tests for the new checks
2. Run only targeted A015 tests with `PYTHONPATH=.` and a focused `-k` filter

Required proof:

Targeted A015 tests pass for the new E-side checks.

Pass condition:

The new failure modes are visible in health logic without needing a live ad-hoc A run.

Automatic next step:

Start Phase 5.

### Phase 5 - Frozen-input proof pack

Status: Complete

Goal:

Prove the corrected outputs are repeatable on the same frozen inputs.

Allowed files:

- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`
- `plans/active/b-e-sales-truth-recovery-v1/FINAL_PASS_CRITERIA.md`

Required command set:

1. `python -m py_compile` for all changed E/A files and related tests
2. `pytest` for:
   - `tests/test_e002_build_roi_snapshot.py`
   - `tests/test_e004_build_performance_summary.py`
   - `tests/test_e006_build_sales_truth_reconciliation.py`
   - `tests/test_e007_build_sku_daily_sales_truth.py`
   - `tests/test_e_split_health_gate.py`
3. `PYTHONPATH=.` targeted `pytest` for the A015 helper coverage
4. Rebuild the isolated E outputs twice from the same frozen inputs

Required proof checks:

1. `sales_truth_reconciliation_latest.csv` mismatch rows remain `0`
2. `sku_performance_summary.csv` no longer publishes mixed economic truth
3. `sku_daily_sales_truth_latest.csv` preserves finalized/provisional distinction
4. Sample SKU `A2-T2AC-TW3L` still matches expected finalized/provisional values

Pass condition:

Two consecutive isolated runs produce the same result against the same frozen baseline.

Automatic next step:

Start Phase 6.

### Phase 6 - Final sign-off classification

Status: Complete

Goal:

Classify the work correctly and stop short of overclaiming.

Allowed files:

- `plans/active/b-e-sales-truth-recovery-v1/PLAN_STATUS.md`
- `plans/active/b-e-sales-truth-recovery-v1/FINAL_PASS_CRITERIA.md`

Required final wording:

- `code fix applied`
- `isolated verification passed`
- `live loop verification pending next cycle check`

What must not be said yet:

- `fully proven live`
- `runtime verified`
- `done` if the next scheduled cycle has not yet confirmed the post-change health

Pass condition:

All coding phases are complete, all scoped tests pass, the frozen-input proof pack is clean, and the remaining live verification dependency is stated plainly.

## Known Sample-Proof Targets

These are the fixed sample expectations Codex should use during execution:

### SKU `A2-T2AC-TW3L`

Finalized truth target:

- date: `2026-04-16`
- source state: `finalized_ledger`
- units: `3`
- revenue: `27.24`
- profit: `1.86`

Provisional truth target:

- date: `2026-04-17`
- source state: `provisional_order_master`
- units: `6`
- revenue: `55.92`
- profit: `4.98`

Comparison note:

- Sellerboard `10.87` is not accepted as system truth because fee values are incomplete.

## Execution Score Model

At the end of each phase, score the phase out of 10 on:

1. coding correctness
2. dataset integrity
3. operator clarity
4. regression protection

No phase is considered complete below `8/10` in any category.

## Stop Conditions

Stop and record the issue if any of these happen:

1. frozen inputs change mid-proof
2. a phase requires a new business interpretation not already written here
3. a test failure shows the root cause is upstream of the current phase
4. the fix would require changing Sheets or running an A script without explicit user approval

## Execution Proof

1. Scoped compile:
   - passed for changed E flow files, `run_E_cycle.py`, A015 helper file, and related tests
2. Scoped tests:
   - `pytest` E suite: `15 passed`
   - `pytest` targeted A015 helpers: `4 passed`
3. Deterministic rebuild:
   - `E002 -> E004 -> E006 -> E007` run twice consecutively
   - output hash diff count: `0`
   - frozen input hash diff count: `0`
4. Sample SKU evidence:
   - `A2-T2AC-TW3L` finalized `2026-04-16`: units `3`, revenue `27.24`, profit `1.86`
   - `A2-T2AC-TW3L` provisional `2026-04-17`: units `6`, revenue `55.92`, profit `4.98`
