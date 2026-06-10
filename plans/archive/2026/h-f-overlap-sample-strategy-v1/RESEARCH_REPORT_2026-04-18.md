# Research Report

## Question
- After the cleanup sign-off, what is the correct next H/F ticket: overlap recovery, sample growth, strategy tuning, or all three?

## Short answer
- It needs to be all three, but in the right order.
- Overlap recovery comes first.
- Sample scoring comes second.
- Strategy tuning comes last and should stay shadow-only until the scorecard says otherwise.

## What the current evidence says

### 1) Cleanup work did its job
- H safety is no longer the blocker.
- Latest signed-off H ceiling slice:
  - `run_id=20260418T102258Z`
  - `61` rows
  - `0` rows where `true_binding_ceiling_gbp < hard_floor_gbp`
- H daily rollups now have `0` impossible rows.
- H state now exposes fresh strategy sample counts with a stale-checklist marker.
- H/F health is clean:
  - `hf_fail=0`
  - `hf_warn=0`
  - `hf_scrape_gap_missing_rate=0.0636`

### 2) The main blocker is overlap, not raw scrape failure
- Foundation metrics show:
  - `identity_rows_with_asin=6979`
  - `identity_rows_asin_in_h_scope=0`
  - `identity_rows_asin_not_in_h_scope=6979`
  - `identity_asin_h_scope_overlap_rate=0.0000`
- This means the bridge code is no longer hiding the issue.
- The issue is that the H/F universes still do not overlap where the ASINs already exist.

### 3) The second blocker is missing expected baseline coverage
- Alignment pack totals:
  - `95` rows total
  - `65` rows `missing_expected_baseline`
  - `24` rows `underperform_vs_expected`
  - `3` rows `outperform_vs_expected`
  - `2` rows `aligned`
  - `1` row `missing_actual_30d`
- Source mix:
  - `no_source=65`
  - `full_capture_asin=30`
  - `assumption_snapshot=0`
  - `sales_validation=0`
- So the strategy review layer still risks confusing "we do not have a baseline" with "the tactic underperformed."

### 4) The third blocker is thin tactic evidence in H
- Current H live tactic counts:
  - `multi_seller_ladder_cap=87/150`
  - `single_rival_reset=5/30`
  - `suppression_reactivation=62/20`
- Latest daily tactic evidence still shows weak maturity in the tactics we want to improve:
  - `multi_seller_ladder_cap`: `88` decisions, `29` failed, `55` expired
  - `single_rival_reset`: `5` decisions, provisional
- This means there is enough signal to build a scorecard, but not enough to justify direct live tuning for those tactics yet.

### 5) The system now has enough raw data to score tactics honestly
- Action outcomes:
  - `12738` rows
  - `eligible_to_write=12218`
  - `decision_to_change_price=439`
  - `write_attempted=2172`
  - `write_applied=2166`
- That is enough raw evidence to build:
  - tactic-level write chain metrics
  - expiry/fail mix
  - realised outcome rollups
  - maturity gates

## What should happen next

### Phase order
1. Build an overlap expansion pack.
2. Build a tactic scorecard and maturity gates.
3. Build an operator review pack that separates:
   - missing baseline
   - true underperformance
   - alignment
   - thin sample
4. Build a shadow-only experiment queue.
5. Only then consider a later H runtime cohort ticket.

### Why this order is correct
- If we start with live strategy tuning, we will still be arguing about overlap and missing baseline instead of strategy truth.
- If we stop at overlap recovery, we still will not know which tactics deserve more time and which deserve a queue entry.
- If we build the queue before the scorecard, we risk promoting tactics that are still thin-sample or mostly expired.

## Numeric starting targets for the next execution ticket
- Overlap phase:
  - recover a nonzero `identity_rows_asin_in_h_scope`, or at minimum produce a deterministic routing pack that explains every ASIN-bearing unresolved row
- Scorecard phase:
  - keep `multi_seller_ladder_cap` and `single_rival_reset` blocked from promotion until they meet or deliberately override their sample gates
- Review phase:
  - preserve the distinction between `missing_expected_baseline` and `underperform_vs_expected`
- Queue phase:
  - every queue row must stay `shadow_only_flag=1`

## Planning conclusion
- The next ticket should not be "change repricer strategy."
- The next ticket should be:
  - `H/F overlap, sample growth, and strategy optimisation v1`
- That ticket should create the overlap pack, scorecard, review pack, and shadow queue first.
