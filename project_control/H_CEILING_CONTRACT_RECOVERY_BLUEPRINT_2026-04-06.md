# H Ceiling Contract Recovery Blueprint

## 1. Purpose

This document defines the planning blueprint to fix the repricer ceiling problem that left ASIN `9188805646` / SKU `LV-425G-BY4X` sitting on floor even when live competition was higher.

This blueprint is for:
- root-cause repair
- code design
- test design
- proof design

This is intentionally written to fit both:
- the current live repricer contract
- the target repricer architecture

References:
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- `project_control/DECISIONS.md`
- `project_control/CURRENT_STATE.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `out/process_guides/repricing_tool/strategy-steps-v1.3.md`
- `out/process_guides/repricing_tool/master plans/masterplan_v10.md`

## 2. Plain-English Summary

The system is meant to calculate a ceiling upstream in A and then use that ceiling in H.

For this SKU, that did not happen.

What actually happened:
- H floor was valid
- live rival pricing existed
- A wrote no usable upward ceiling
- H knew it should raise
- H had no trusted bound to raise against
- price stayed on floor

The temporary H fallback patch stops the bad outcome.

The real repair is:
- make A produce a truthful upward ceiling contract
- keep floor protection separate from upward opportunity
- make H use that contract
- keep live-rival fallback as degraded safety, not as primary design

## 3. Blueprint Fit With Masterplan And Live Contract

This blueprint follows the masterplan and current runtime rules rather than inventing a new pricing model.

From `masterplan_v10.md`:
- hard floor is sacred
- three ceilings must remain separate
- ceilings clamp before optimisation
- CPT is risk telemetry in Phase 1, not a general target setter
- execution must be explainable with source and reason codes

From `strategy-steps-v1.3.md` and current live code:
- H is already multi-SKU and event-driven inside the H runtime
- current A/H stack still carries Phase 1 ceiling logic
- current live implementation still uses `ceiling_rule_value_gbp` and `ceiling_inputs_missing_flag`

From `project_control/DECISIONS.md`:
- repricer planning cleanup belongs in `project_control`
- ceiling fallback and CPT wording drift is already a known conflict
- the live contract and target architecture must be kept distinct

This blueprint therefore does not try to jump straight to a full repricer redesign.
It fixes the current contract first, in a way that moves it closer to v10.

## 4. Problem Statement

Observed live issue for SKU `LV-425G-BY4X` on `2026-04-06`:
- floor was `23.87`
- VAT rate was `0`
- our price was `23.87`
- lowest FBA was `23.87` (us)
- lowest FBM was `26.28`
- H state was `RAISE_FIND_LOSS`
- daily intel had `ceiling_rule_value_gbp` blank
- daily intel had `ceiling_inputs_missing_flag = 1`
- daily intel also had blank FOEP, blank CPT, blank manual cap

This created a broken chain:

1. A016 resolved no manual cap.
2. A016 resolved compliance anchor from market price.
3. `run_a_cycle()` wrote a valid compliance ceiling but no valid upward ceiling.
4. H consumed the blank upward ceiling context.
5. H entered a raise state with no proper bound.
6. Price stayed on floor.

## 5. Root-Cause Theory

The real defect is not only "ceiling missing".

It is a contract-design problem with three parts.

### 5.1 Upward ceiling and floor protection are mixed together

Current A logic can produce:
- `compliance_ceiling_landed_gbp`
- `eligibility_ceiling_landed_gbp`
- `ceiling_rule_value_gbp`

But in the failure case:
- compliance ceiling became the same general area as current price / floor protection
- `ceiling_rule_value_gbp` was blank
- H had no separate "safe price space above current price" contract

That means a defensive protection number was treated like a full upward ceiling contract.

### 5.2 Manual-cap sourcing is too narrow

Current A016 `_resolve_manual_cap()` only uses:
- `config/phase1_manual_max_caps.csv`
- optional config fallback

It does not currently recover a cap from a broader approved source path.

For this SKU, manual cap stayed blank for days.

### 5.3 A writes semantic shortcuts that hide the real source

Current A016 passes:
- `bbp_max_sold_gbp = manual_cap`

That means BBP and manual-cap semantics are collapsed together even when there is no real BBP value.

This makes the ceiling chain harder to debug and easier to leave blank silently.

## 6. Target State

The repaired system should expose three separate truths:

1. Floor truth
- "how low can we ever go"

2. Protection truth
- "what policy / compliance guard still limits price"

3. Upward opportunity truth
- "what trusted bound allows a raise from current price"

The required rule is:
- H may not use floor protection as a substitute for upward opportunity

The required behavior is:
- if upward opportunity exists, H may raise within that bound
- if upward opportunity is missing, H must say it is missing explicitly
- if live-rival fallback is used, it must be reason-coded as degraded fallback, not mistaken for normal ceiling intelligence

## 7. Data Contract Changes

### 7.1 New daily-intel contract fields

Add these fields to `sku_daily_intel`:
- `upward_ceiling_gbp`
- `upward_ceiling_source`
- `upward_ceiling_confidence`
- `upward_ceiling_inputs_missing_flag`
- `upward_ceiling_reason_codes_json`
- `ceiling_contract_status`
- `manual_cap_source`
- `bbp_source`

Recommended `ceiling_contract_status` values:
- `OK`
- `MISSING`
- `DEGRADED`
- `LIVE_FALLBACK_ONLY`

### 7.2 Backward compatibility

Keep existing fields during migration:
- `ceiling_rule_value_gbp`
- `ceiling_source_used`
- `ceiling_inputs_missing_flag`

But treat them as legacy compatibility fields until readers are migrated.

### 7.3 Runtime observability additions

Add the new ceiling contract fields to:
- `out/phase1_daily_intel_latest.csv`
- `out/phase1_runtime_floor_snapshot_latest.csv` where relevant summary fields are already published
- H observation outputs if they surface pricing state to operators

## 8. Source Authority And Resolution Order

### 8.1 Manual cap resolution

Replace the current narrow manual-cap logic with explicit source order:

1. `config/phase1_manual_max_caps.csv`
2. approved Product DB cap field, if one exists and is mapped explicitly
3. optional config default only if the repo setting explicitly allows it

Important rule:
- Product DB may only be used if the exact cap field is named and approved
- do not infer a cap from arbitrary sheet columns without naming the column in code and tests

### 8.2 Compliance anchor resolution

Keep compliance anchor separate from upward ceiling.

Compliance anchor source order can stay:
1. explicit configured compliance anchor
2. manual cap
3. buy box
4. our price

But this value must not be mistaken for "raise target available".

### 8.3 Upward ceiling resolution

Create one explicit helper for upward ceiling contract resolution.

Recommended current-contract source order:
1. approved BBP / max-sold ceiling
2. approved CPT-derived ceiling if current Phase 1 policy still permits it
3. explicit FOEP-based eligibility ceiling when available and sane
4. explicit last-known-safe ceiling when it has a real numeric value
5. blank with `MISSING` status if none of the above exist

Important rule:
- compliance anchor is not part of the upward ceiling ladder

## 9. Coding Plan

## 9.1 Phase 0 - Contract helper split

Files:
- `scripts/phase1/phase1_storage.py`
- `scripts/phase1/phase1_ceilings.py`

Work:
- add schema fields
- add a new dataclass for upward ceiling contract
- add one helper that resolves the upward ceiling with source, confidence, and reason codes

Required code outcome:
- floor logic
- compliance logic
- upward ceiling logic

must be separate functions with separate outputs

## 9.2 Phase 1 - A016 source repair

Files:
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`

Work:
- split `_resolve_manual_cap()` from any BBP logic
- add explicit source tagging
- add explicit Product DB cap fallback only if an approved field is mapped
- stop passing `bbp_max_sold_gbp=manual_cap` unless that value really is the BBP/ceiling input intended by policy

Required code outcome:
- manual cap can be missing without silently pretending BBP exists
- source path is visible in output rows

## 9.3 Phase 2 - A-cycle contract write repair

Files:
- `scripts/phase1/phase1_main_loop.py`

Work:
- extend `run_a_cycle()` to write the new upward ceiling contract
- leave compliance and eligibility outputs intact
- populate `ceiling_contract_status`
- set missing/degraded reason codes truthfully

Required code outcome:
- A writes a real upward ceiling contract
- missing contract becomes explicit and machine-checkable

## 9.4 Phase 3 - H-cycle consumer migration

Files:
- `scripts/phase1/phase1_main_loop.py`
- possibly `scripts/flows/H/H110_run_phase1_h_pilot.py` if wrapper fields need to be surfaced

Work:
- migrate H raise logic to prefer `upward_ceiling_gbp`
- treat legacy `ceiling_rule_value_gbp` as compatibility only
- keep live-rival fallback behind explicit degraded reason codes

Required rule:
- H uses normal contract first
- live-rival fallback only activates when normal contract is missing
- fallback never hides the missing-upstream condition

## 9.5 Phase 4 - Health and dashboard proof

Files:
- `scripts/flows/A/A015_build_system_health_check.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`

Work:
- add a scoped health check for repeated missing upward ceilings on active repricing SKUs
- add dashboard visibility for:
  - upward ceiling source
  - ceiling contract status
  - fallback usage

Required health outcome:
- repeated missing ceiling contracts become visible as health truth
- operators can tell the difference between:
  - normal calculated ceiling
  - degraded fallback
  - missing contract

## 10. Theory Resolution

The theoretical fix is:
- upward opportunity must be its own contract

The coding translation is:
- stop letting a compliance anchor behave like a full upward ceiling
- stop letting blank cap inputs disappear without a named status
- give H one explicit upward ceiling field to consume

This resolves the issue in both theory and code because:
- the model becomes structurally correct
- the same defect class becomes testable
- the health system can catch the upstream break instead of only the downstream symptom

## 11. Test Blueprint

## 11.1 Unit tests

Add or extend tests for:
- `scripts/phase1/phase1_ceilings.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`

Required cases:
- manual cap only
- CPT-derived ceiling only
- BBP plus CPT ceiling with correct chosen source
- all upward sources missing
- compliance anchor present but upward ceiling missing
- last-known-safe present and valid
- last-known-safe source declared but numeric value blank

## 11.2 H behavior tests

Required cases:
- `RAISE_FIND_LOSS` with valid upward ceiling raises above current price
- `RAISE_FIND_LOSS` with missing upward ceiling does not pretend success
- live-rival fallback activates only in the degraded branch
- `CPT_RISK_UNKNOWN` still blocks ordinary upward moves outside the approved degraded branch

## 11.3 Schema and contract tests

Required cases:
- `sku_daily_intel` schema includes new fields
- new fields are populated or blank according to contract rules
- no row may claim `ceiling_contract_status=OK` with blank `upward_ceiling_gbp`
- fallback rows must carry explicit fallback reason codes

## 11.4 Health tests

Required cases:
- active write-eligible SKU with repeated missing upward ceiling triggers WARN or FAIL according to policy
- stale or missing upstream contract is surfaced as upstream truth, not disguised as generic repricer behavior

## 11.5 Fixture replay test

Add one regression fixture that matches the live defect class:
- current price at floor
- live rival above current price
- missing FOEP
- missing CPT
- missing manual cap
- valid compliance anchor

Expected result:
- A writes explicit missing or degraded upward ceiling contract
- H either uses normal repaired ceiling contract or degraded live fallback with explicit reason codes
- H no longer sits on floor silently

## 12. Proof Blueprint

## 12.1 Isolated proof

Required before any runtime claim:

1. unit and contract tests pass
2. fixture replay passes
3. direct row inspection shows the repaired daily-intel contract for a defect-class fixture

Minimum proof commands:
- targeted `pytest` for A016 / phase1 ceiling helpers / H main loop
- targeted schema and health tests

Required proof artifacts:
- before/after example daily-intel row
- before/after H decision example
- reason code evidence

## 12.2 Runtime proof

Because this repo forbids ad-hoc A runs by default, runtime proof should use scheduler-owned evidence unless explicitly requested otherwise.

Required runtime chain:
1. A016 writes a fresh daily-intel row after code change
2. A015 health reflects the new ceiling contract truth
3. H consumes the fresh contract on the next scheduled cycle
4. target SKU is no longer stuck at floor when safe upward space exists

Required runtime evidence for success:
- fresh `data/sku_daily_intel.csv` row after code change
- fresh `out/system_health_checklist.csv` / H-scoped gate after code change
- fresh `out/phase1_runtime_floor_snapshot_latest.csv` row after code change
- H run reaches terminal success state with finalized evidence

## 12.3 Success language

The implementation ticket must separate:
- code fix applied
- isolated verification passed
- live loop verification pending
- live loop verification confirmed

Do not call the upstream repair complete until the live proof chain exists.

## 13. Non-Goals

This blueprint does not:
- redesign the whole repricer
- remove the temporary H fallback immediately
- change suppression architecture
- change portfolio governor behavior
- absorb the unrelated unknown-outcome / observability test failures into this ticket

Those are separate work items unless a later trace proves they are coupled.

## 14. Delivery Tickets

Recommended ticket order:

1. Ceiling contract split in phase1 helpers and storage schema
2. A016 source repair and explicit cap-source logging
3. A-cycle daily-intel writer migration
4. H-cycle consumer migration
5. A015 and H130 health / observability rollout
6. live proof review and contract wording cleanup in project-control docs

## 15. Definition Of Done For This Blueprint

This issue is only done when all are true:
- A writes a separate upward ceiling contract
- compliance anchor is no longer treated as a substitute upward ceiling
- H consumes the repaired contract
- missing upward ceilings are visible in health outputs
- targeted tests pass
- fixture replay passes
- live scheduled evidence confirms the target defect class is gone

## 16. Known Parallel Alert

There is already a separate alert in current validation:
- two unrelated `unknown_outcome / observability` tests are failing in `tests/test_phase1_main_loop.py`

This blueprint does not merge that issue into the ceiling-contract repair.
It should be tracked separately unless new evidence shows the same root cause.
