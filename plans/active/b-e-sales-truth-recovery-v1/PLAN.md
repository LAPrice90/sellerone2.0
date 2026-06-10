# B/E Sales Truth Recovery v1

## Purpose

Recover trustworthy SKU sales and profit reporting so the repricer and operator reports can use real order truth instead of mixed signals.

Execution for this plan is complete under isolated proof. The remaining dependency is the next scheduled live-loop health snapshot after the code-change timestamp.

The goal moved from "mostly corrected" to "fully provable" and that isolated proof has now been achieved.

## Plain-English Problem Statement

We found three separate truths being treated as if they were one:

1. Finalized order truth from `out/order_ledger_fx.csv`
2. Provisional same-day order truth from `out/order_master.csv`
3. Sellerboard/operator expectations, which can be incomplete when fee values are missing

That caused two operator-facing problems:

1. A SKU could show correct revenue and profit, but the wrong unit count
2. A "today" answer could mix finalized and provisional information without saying which one it was

That is why a SKU like `A2-T2AC-TW3L` could look wrong at first glance:

- Sellerboard today estimate: `10.87` profit
- Current raw provisional order data: `5` sales, `4.15` profit
- Latest finalized B-ledger day: `3` sales, `1.86` profit

The system needs to say which of those is finalized truth, which is provisional, and which is external-only context.

## Source-of-Truth Rules

These rules are now fixed for this plan and should not be changed mid-execution:

1. `out/order_ledger_fx.csv` is the canonical finalized sales truth for profit and revenue.
2. `out/order_master.csv` is allowed only for provisional same-day visibility when finalized ledger truth is not available yet.
3. Sellerboard is comparison context only. It is not system truth when fee fields are missing.
4. No downstream file may "smooth over" a mismatch by relabelling mixed numbers as a single truth.

## What Is Already Working

The following work is already in place and has isolated proof:

1. `scripts/flows/E/E002_build_roi_snapshot.py`
   - Now prefers `order_ledger_fx`
   - Falls back cleanly when needed
   - Handles index alignment correctly
   - Handles missing COGS and missing column cases more safely

2. `scripts/flows/E/E006_build_sales_truth_reconciliation.py`
   - Produces reconciliation outputs
   - Current mismatch rows are `0`

3. `scripts/cycles/run_E_cycle.py`
   - Includes the reconciliation builder in the E flow

4. `scripts/flows/A/A015_build_system_health_check.py`
   - Has new E-side health helpers for sales-truth integrity
   - Has unit tests for the new helpers

5. Targeted isolated tests already passed for the new E002, E006, and A015 helper work

## What Is Still Not Finished

These are the only remaining closeout items:

1. Wait for the next scheduled cycle to confirm post-change live-loop health.
2. Keep the new daily-truth output integrated in operator review so finalized and provisional values are not mixed in manual interpretation.

## Delivery Rule For The Rest Of This Plan

From this point onward the work must be executed under a frozen-input rule:

- No new business interpretation
- No new external reference source
- No silent source switching mid-phase
- No "close enough" downstream patching

Each phase must:

1. change only its allowed files
2. run only its scoped tests
3. produce written proof before the next phase starts

## Required Deliverables

This plan is complete only when all of these exist and pass:

1. Corrected `E004` performance summary logic
2. New daily sales-truth output with explicit finalized/provisional status
3. E cycle wiring for the new daily truth output
4. A015 helper coverage for the new E-side checks
5. A frozen-input proof pack with repeatable results
6. A final pass checklist showing the ticket is ready for sign-off

## Phase Map

### Phase 0 - Freeze the evidence baseline

Lock the exact input files and expected proof targets before any more coding.

### Phase 1 - Fix mixed-unit performance summary logic

Remove the current unit-count mixing in `E004` so performance outputs stop combining velocity counts with finalized money.

### Phase 2 - Add explicit daily sales truth

Create a new daily output that answers:

- what is finalized
- what is provisional
- what confidence level the operator should assign to it

### Phase 3 - Wire the daily truth into E flow

Make the new output part of the normal E build and ensure the output is treated as a first-class artifact.

### Phase 4 - Extend health coverage

Add health/helper checks so future regressions are visible and testable.

### Phase 5 - Build the frozen-input proof pack

Run the isolated command set twice against the same frozen inputs and confirm the outputs stay consistent.

### Phase 6 - Final sign-off gate

Apply the final pass criteria and classify the result correctly as:

- code fix applied
- isolated verification passed
- live loop verification pending next scheduled cycle check

## Current Readiness Rating

- Coding foundation: 9/10
- Root-cause clarity: 9/10
- Dataset trust: 8/10
- Sign-off readiness: 9/10 (isolated), 7/10 (live-loop pending)

The coding phases and frozen-input proof are complete. The remaining step is live-loop confirmation on the next scheduled cycle window.
