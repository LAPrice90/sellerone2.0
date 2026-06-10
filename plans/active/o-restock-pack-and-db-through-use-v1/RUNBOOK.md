# Runbook

## Purpose
- What this plan or system does:
  - It gives a slow, simple path to build the next restock version around real operator use, starting with fake SKU data before touching real product records.

## Standard run order
```powershell
# Phase 0 is planning only. No runtime command is required yet.

# When Batch 001 starts, begin with the mock scenarios in:
# plans/active/o-restock-pack-and-db-through-use-v1/MOCK_SKU_SCENARIOS.csv

# Then run targeted O tests only after implementation work begins.
```

## Validation steps
- Step 1:
  - Read the fake SKU scenarios and confirm each one makes sense in plain English.
- Step 2:
  - Check that each scenario answers one simple question:
    - what do we buy from the supplier?
    - what do we sell on Amazon?
    - what unit should the operator type into `Ordered`?
- Step 3:
  - Only after the mock rows feel right, map a very small real-SKU sample.

## Expected outputs
- Output:
  - Mock quantity-profile behavior
- Path:
  - `plans/active/o-restock-pack-and-db-through-use-v1/MOCK_SKU_SCENARIOS.csv`
- What good looks like:
  - a non-coder can explain each row without reading code

- Output:
  - Pack-aware O source/UI fields
- Path:
  - future O outputs under `out/systems/O/live/`
- What good looks like:
  - the operator sees clear order meaning, not hidden maths

## Health checks
- Check:
  - current repo health warnings
- Pass condition:
  - no FAIL affecting O inputs
- Warning condition:
  - non-O warnings exist but do not block planning
- Fail condition:
  - upstream O input truth becomes missing or contradictory

- Check:
  - pack truth completeness for each row
- Pass condition:
  - quantity mode and required conversion fields are present
- Warning condition:
  - optional quantity helpers are missing
- Fail condition:
  - operator quantity cannot be converted safely

## Failure recovery
- If input is stale:
  - treat old O summaries as stale context and do not present them as proof
- If output is missing:
  - fall back to mock scenarios and document the missing real field explicitly
- If tests fail:
  - stop and name the exact scenario that broke
- If runtime ownership is unclear:
  - do not start live-loop work; keep the ticket in mock-data mode

## Slow and simple walkthrough
- 1. Start with `SKU-MOCK-UNIT-1`.
  - This is the easiest case.
  - We buy one unit.
  - We sell one unit.
  - If the system says order `12`, that means `12` real units. No conversion.

- 2. Move to `SKU-MOCK-CASE-12`.
  - The supplier sells in cases of `12`.
  - We still sell one unit at a time.
  - If the operator wants `24`, the system should explain that this means `2` supplier cases.

- 3. Move to `SKU-MOCK-REPACK-3`.
  - The supplier sends raw units in cases.
  - We sell Amazon packs of `3`.
  - The operator should think in sell packs, not raw units.
  - The system must do the hidden conversion and tell us whether the order is valid against supplier case rules.

- 4. Move to `SKU-MOCK-BUNDLE-2X`.
  - We buy one shape.
  - We sell another shape.
  - The system must make the bundle math visible enough that you can trust it without manual calculation.

- 5. Only after those four feel simple should we bring in any real SKU.

## Archive note
- What to preserve when this plan is finished:
  - the mock scenarios
  - the final quantity vocabulary
  - the chosen v1 data boundary for pack truth
