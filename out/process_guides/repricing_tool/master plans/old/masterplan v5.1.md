# Masterplan v5.1 — Unified Repricing Intelligence + Delivery Value Engine + Three-Ceiling Governance + Pressure State

Status: Active Draft (Unified v5.1)  
Date: 2026-02-12  
Owner: Luke (business intent), Codex (execution support)

## 0) What Changed vs v5 (diff guide)
1. **Core v4 safety and fallback logic is restored**
   - Explicit fallback chains are re-added for missing compliance and eligibility inputs.
   - Missing-ceiling handling is made explicit: continue only with a safer ceiling, else escalate.
2. **Decision-flow detail is restored for normal states**
   - Ladder construction rules, candidate estimation fields, tie-breakers, and negative-profit escalation are explicit again.
3. **Portfolio and logging observability are restored**
   - Lane threshold mapping and `portfolio_reason_code` are explicit.
   - Eligibility logging and missing reason codes are restored.
4. **Rollout continuity is restored**
   - Eligibility, demand learning, DVE multiplier learning, and event-driven refresh stages are restored after pressure workflow stages.
5. **Pressure-state improvements from v5 remain fully intact**
   - Manual execution gating, pressure case workflow, and anchor safety constraints remain unchanged.

---

## 0.1) What Changed vs v4 (diff guide)
1. **Pressure/Nuclear Mode is now fully formalised as a Strategy State (not a reflex)**
   - Pressure is treated as **capital allocation strategy**, not “repricing logic”.
   - **Automation may detect + score + recommend**, but **cannot execute** pressure actions.
2. **Pressure Qualification Framework is now mandatory**
   - Opponent validation
   - Profit uplift model (expected gain must be positive)
   - Resource check (stock/cash/ops)
   - Compliance + CPT anchor distortion check
3. **A Pressure Case layer + logging are added**
   - Every activation creates a `pressure_case_id` with full justification, plan, and outcomes.
4. **State machine + transition rules are explicit**
   - Normal pricing states remain profit-led.
   - Pressure is time-boxed and has automatic exit conditions and cooldown.
5. **CPT anchor risk is treated as a first-class constraint**
   - Pressure actions must obey a **price-history safety floor** to avoid permanently lowering future ceiling.

---

## 1) Canonical Rule (Single Source of Truth)
- This file is the only authoritative repricing plan going forward.
- Any other plan files are reference/archive unless their content is explicitly copied into this file.

---

## 2) Goal
Build a repricing system that:
- **Maximises expected sustainable profit per day** under competitive constraints (default).
- Supports **aggressive tactics** (share capture / floor discovery / pressure) only when rational, never as default.
- Learns from **real Buy Box outcomes** and **seller behaviour**, not just visible “lowest price”.
- Prices the economic reality that:
  - **Delivery speed has monetary value** (Delivery Value Engine).
  - **Eligibility signals (FOEP/CPT) constrain feasible pricing**.
  - **Demand has a ceiling** even when eligible and compliant.
- Scales from one pilot SKU to broad coverage with strict guardrails and explainability.

---

## 3) Non-Negotiables
1. **Default objective is profit optimisation**: never “lowest winning price” by default.
2. **Hard floor is sacred**: never breached, for any mode.
3. **Effective price is mandatory**: competitiveness comparisons use *effective price* (landed + delivery penalty).
4. **Three ceilings must remain separate**:
   - Compliance (policy)
   - Eligibility (Buy Box feasibility)
   - Demand (conversion realism)
5. **Ceilings clamp before optimisation**: the optimiser never sees “forbidden” price space.
6. **Strategy unit is `SKU + seller_id`**: learning and behaviour are seller-specific.
7. **Learning is behaviour-triggered**: re-enter learning on drift/unknowns; calendar checks are only backup.
8. **Market structure integrity**: if market changes during a test, learning confidence must be invalidated.
9. **Execution must be explainable**: reason codes + confidence + logged pre/post estimates.
10. **Aggression is an explicit override**: gated, time-boxed, measurable, with kill conditions.
11. **Eligibility intelligence never writes prices**: FOEP/CPT constrain or warn; they do not set targets.
12. **No "delivery = stock" inference**: delivery windows are competitiveness signals only and must not be treated as inventory truth.
13. **Portfolio Governor is mandatory daily**: SKUs must pass a fight-worthiness gate before high-cadence tactics.
14. **Seller priority is mandatory weighting**: `ignore/exploit/neutral/defend/pressure_candidate` must affect cadence and ladder behaviour.
15. **Pressure state is manual-execution only**:
    - system can recommend
    - Supervisor can recommend
    - **Head must approve**
    - no autonomous extensions

---

## 4) Operating Model (Roles)

### Head (Boundaries + Intent + Capital Allocation)
Sets per-SKU boundaries and intent **before** any optimisation runs.

Minimum set:
- `hard_floor_price_gbp`
- `soft_floor_price_gbp`
- `target_roi_band_pct`
- `today_intent` (default: `maximize_profit`)
- `api_budget_tier` / cadence limits
- Optional: `manual_cap_price_gbp` (only if explicitly reason-coded)

Pressure-specific authority:
- approves `OBJ_PRESSURE_MANUAL` activations (pressure is capital strategy).

### Supervisor (Mode + Plan Approval)
Chooses objective state (default profit; optional overrides).  
Approves ladder depth, max move, cooldown, probe style.  
May recommend pressure, but cannot activate without Head approval.

### Optimiser (Profit Engine)
Builds candidate ladder within boundaries + ceilings.  
Uses seller-game learning + Delivery Value Engine (effective-price space) to estimate:
- win probabilities / share
- expected units/day
- profit per unit
- expected profit/day per candidate

Recommends the price that maximises expected profit/day subject to constraints.

### Pressure Analyst (Recommendation Engine)
Produces pressure candidates and a pressure feasibility score.
It may:
- classify opponent type
- estimate probability of exit
- estimate margin loss during pressure
- estimate post-exit uplift and expected gain
- propose a time-boxed plan and kill conditions

It may **not**:
- write prices
- extend a pressure campaign

### Executioner (Write + Observe + Log)
Executes only approved actions.
- normal states: executes Optimiser-selected action (Supervisor-approved)
- pressure state: executes the **pre-approved pressure plan** (time-boxed)
Logs actions + response windows + measured outcomes.  
Updates learning memory only when market structure is stable and confidence rules allow.

---

## 5) System Architecture (Modules + Cadence)

### 5.1 Data Layers (must be physically separate)

1) **Offer Instance Layer (event-level truth)**
- raw offer snapshot per cycle
- `listing_price_gbp`, `shipping_gbp`
- delivery window (`min_days`, `max_days`)
- channel (FBA/FBM/Amazon/etc.), Prime flag if available
- promo/coupon suspected flags
- timestamp
- market structure fields (see §14)

2) **Persistent Seller Memory Layer (behavioural model)**
Per `SKU + seller_id`:
- delta learning:
  - `learned_delta_effective_gbp`
  - `highest_delta_win_effective_gbp`
  - `lowest_delta_loss_effective_gbp`
  - `delta_confidence`
- behaviour:
  - `reaction_speed`
  - `persistence_score`
  - `capital_depth_score`
  - `margin_tolerance_estimate`
  - `seller_floor_confidence` **(new: confidence they will chase down / have room)**
  - `non_reactive_score` **(new: probability they will not chase)**
  - `opponent_type` **(new: amazon_retail | brand_direct | distributor_clearance | low_stock | normal_unknown)**
- integrity:
  - `promo_suspected_flag`

3) **Delivery Model Layer (SKU-level)**
Per `SKU` (or SKU-cluster if needed):
- `delivery_penalty_curve_version`
- `delivery_penalty_multiplier_sku` (default 1.00)
- `delivery_confidence`
- `last_delivery_model_update_utc`

4) **Eligibility Intelligence Layer (SKU-level, daily)**
Per `SKU`:
- `foep_price_gbp` (Featured Offer Expected Price)
- `competitive_price_threshold_gbp`
- `eligibility_confidence`
- `eligibility_last_refresh_utc`

5) **Compliance Intelligence Layer (SKU-level, daily)**
Per `SKU`:
- `external_reference_price_gbp` (optional)
- `policy_buffer_pct`
- `compliance_confidence`
- `compliance_last_refresh_utc`

6) **Demand Model Layer (SKU-level, slow)**
Per `SKU`:
- `demand_ceiling_effective_gbp` (defined in effective-price space)
- `demand_confidence`
- `demand_model_version`
- `demand_last_refresh_utc`
- Optional interim fields:
  - `bbp_max_sold_price_gbp` (temporary safe-mode proxy)
  - `historical_price_band_edges_gbp`
  - `conversion_inflection_effective_gbp`

7) **Ceiling Engine Output Layer (SKU-level, computed)**
Per `SKU` per day (A-cycle baseline) and per H-cycle snapshot (event-level):
- `compliance_ceiling_landed_gbp`
- `eligibility_ceiling_landed_gbp` (combined)
- `eligibility_ceiling_landed_signal_gbp`
- `eligibility_ceiling_landed_market_gbp`
- `demand_ceiling_landed_gbp`
- `final_ceiling_landed_gbp`
- `binding_ceiling_type` (`compliance|eligibility|demand|manual`)
- `ceiling_confidence_overall`
- `ceiling_reason_codes[]`

8) **Portfolio Governor Layer (SKU-level, daily)**
Per `SKU`:
- `listing_worth_fighting_score`
- `aggressor_probability`
- `capital_lockup_factor`
- `delivery_competitiveness_factor`
- `portfolio_lane` (`fight`, `defend`, `exploit`, `ignore`)
- `portfolio_gate_status` (`pass`, `restricted`, `fail`)
- `pressure_allowed_flag` **(new: only true if lane=fight and economics justify)**

9) **Seller Priority Layer (SKU + seller_id)**
Per `SKU + seller_id`:
- `seller_priority_level` (`ignore`, `exploit`, `neutral`, `defend`, `pressure_candidate`)
- `priority_confidence`
- `priority_last_refresh_utc`
- `priority_reason_code`

10) **Pressure Strategy Layer (case-level, new)**
Per `pressure_case_id`:
- identity:
  - `sku`
  - `target_seller_id`
  - `case_created_utc`
  - `case_status` (`draft|recommended|approved|active|ended|aborted`)
- qualification inputs:
  - opponent validation fields + thresholds used
  - profit model inputs + outputs
  - resource check inputs + outputs
  - compliance/CPT anchor checks + outputs
- plan:
  - `pressure_start_utc`
  - `pressure_end_utc` (hard stop)
  - `max_pressure_days` (default 5)
  - `pressure_floor_price_gbp` (>= hard floor and >= anchor floor)
  - `max_daily_cut_gbp`
  - `cooldown_days_after` (default 3–7)
  - `exit_triggers[]`
  - `kill_conditions[]`
- economics:
  - `pressure_profit_per_day_est`
  - `expected_post_exit_profit_per_day_est`
  - `probability_of_exit_est`
  - `expected_uplift_days_est`
  - `expected_gain_est_gbp`
- approvals:
  - `supervisor_recommendation_utc`
  - `head_approval_utc`
  - `approval_reason_code`
- outcomes:
  - `ended_reason_code`
  - measured margin and volume deltas
  - whether competitor exited/retreated/returned

---

### 5.2 Two Operating Cycles

#### A-Cycle (Daily Intelligence Build) — once/day per SKU
- Pull FOEP + CompetitivePriceThreshold.
- Refresh compliance inputs (external reference price if used; policy buffer).
- Update (or carry forward) demand model state (slow cadence; weekly or when enough data).
- Run Portfolio Governor scoring and lane assignment (including pressure-allowed).
- Refresh seller priority levels from behaviour + economics.
- Compute and store baseline ceiling outputs (not snapshot-specific).
- Pressure Analyst may generate *recommendations* (no writes).

#### H-Cycle (Execution / Optimisation) — event-driven + safety polling fallback
On offer change or scheduled check:
1. snapshot market offers
2. compute effective prices (Delivery Value Engine)
3. compute snapshot-specific ceilings (Ceiling Engine)
4. resolve **Strategy State** (normal vs pressure)
5. if normal: run profit optimisation inside floors/ceilings
6. if pressure: follow the approved pressure plan schedule (no optimisation)
7. propose/execute action (approvals + guardrails)
8. log + observe + update learning (if stable)

---

## 6) Core Definitions (Canonical)
- `landed_price_gbp = listing_price_gbp + shipping_gbp`

### Effective price (Delivery Value Engine space)
For any offer **i**:
- `fastest_delivery_days = min(offer.min_delivery_days for offers in snapshot)`
- `delivery_gap_days_i = offer_i.min_delivery_days - fastest_delivery_days`
- `delivery_penalty_gbp_i = DVE_penalty(delivery_gap_days_i) * delivery_penalty_multiplier_sku`
- `effective_price_gbp_i = landed_price_gbp_i + delivery_penalty_gbp_i`

Rules:
- delivery penalty is **non-negative**
- delivery penalty is **0** for the fastest offer(s)

### Ceiling rule (important)
- **Optimisation, learning, and competition comparisons are done in effective-price space.**
- **All ceilings ultimately clamp our landed price** (because Amazon pricing + listing price are landed-price constructs), but:
  - demand ceiling is learned in effective space and translated to landed space per snapshot
  - market-based eligibility is computed in effective space and translated to landed space per snapshot

---

## 7) Delivery Value Engine (DVE)

### 7.1 Why it exists
Price-only logic is incomplete: two sellers at the same visible price are not equal if one delivers tomorrow and one delivers in 3 days.

DVE converts delivery posture into a monetary penalty used in competitiveness comparisons and optimisation.

### 7.2 Layer 1 — Bootstrap Heuristic (Always On)
Default conservative curve (v0):
- gap 0 days → £0.00
- gap 1 day  → £0.15
- gap 2 days → £0.30
- gap 3 days → £0.45
- gap 4+ days → £0.60 (cap)

Implementation:
```text
gap = clamp_int(delivery_gap_days, min=0, max=4)
penalty_base = [0.00, 0.15, 0.30, 0.45, 0.60][gap]
delivery_penalty_gbp = penalty_base * delivery_penalty_multiplier_sku
```

### 7.3 Layer 2 — Eligibility Signal Overlay (FOEP + CPT)
Eligibility signals do not write prices. They act as:
1) ceiling constraints (don’t waste probes above eligibility reality)
2) diagnostics (warn when your model is structurally misaligned)

Daily store:
- `foep_price_gbp`
- `competitive_price_threshold_gbp`
- `eligibility_confidence`

Signal-based eligibility ceiling (landed-price):
```text
eligibility_ceiling_landed_signal_gbp =
  min(foep_price_gbp, competitive_price_threshold_gbp)
```

### 7.4 Layer 3 - Learned Correction (Slow Adaptive Adjustment)
Parameter:
- `delivery_penalty_multiplier_sku` (default 1.00)
- bounds: 0.50 to 2.00

Update only when ALL are true:
- minimum stable events (`min_delivery_events >= N`, start N=20)
- `market_structure_hash` stable during those events
- promo/coupon not suspected
- consistent undercut bias across time and sellers

### 7.5 DVE outputs (must be logged per cycle)
Per offer instance:
- `min_delivery_days`
- `max_delivery_days`
- `delivery_gap_days`
- `delivery_penalty_gbp`
- `effective_price_gbp`

Per SKU per cycle:
- `fastest_delivery_days`
- `delivery_penalty_multiplier_sku`
- `delivery_penalty_curve_version`
- `delivery_penalty_unknown_flag`

---

## 8) Three-Ceiling Model (Canonical)

### 8.1 Compliance Ceiling (Policy / Suppression Safety) — landed-price
Inputs:
- `competitive_price_threshold_gbp` (CPT)
- `external_reference_price_gbp` (optional)
- `policy_buffer_pct` (recommended 0.02–0.05)

Computation:
```text
compliance_anchor = min(competitive_price_threshold_gbp, external_reference_price_gbp?) 
compliance_ceiling_landed_gbp = compliance_anchor * (1 - policy_buffer_pct)
```

Rules:
- Always on.
- Hard clamp (cannot be overridden autonomously).
- If compliance inputs are missing, mark low confidence and fall back in this order:
  - use `competitive_price_threshold_gbp` only (if present)
  - else use last known compliance ceiling
  - else escalate (`FAIL_NO_SAFE_COMPLIANCE_CEILING`)

### 8.2 Eligibility Ceiling (Buy Box Feasibility) — landed-price
Eligibility ceiling has two independent sources:

#### A) Signal-based eligibility ceiling (FOEP/CPT)
```text
eligibility_ceiling_landed_signal_gbp = min(foep_price_gbp, competitive_price_threshold_gbp)
```

#### B) Market-based eligibility ceiling (DVE-adjusted, effective-price game)
1) `best_rival_effective_gbp = min(effective_price_gbp_i excluding ours)`
2) `required_undercut_effective_gbp = f(learned_delta_effective_gbp, confidence, seller mix)`
3) `max_winning_effective_gbp = best_rival_effective_gbp - required_undercut_effective_gbp`
4) translate:
```text
eligibility_ceiling_landed_market_gbp = max_winning_effective_gbp - our_delivery_penalty_gbp
```

Combine:
```text
eligibility_ceiling_landed_gbp =
  min(eligibility_ceiling_landed_signal_gbp?, eligibility_ceiling_landed_market_gbp?)
```

Fallbacks when FOEP is missing:
- Use market-based eligibility ceiling (preferred).
- If market-based cannot be computed (no rivals / insufficient learning):
  - fallback to historical highest winning effective price:
    - `eligibility_ceiling_landed ~= highest_winning_effective_gbp - our_delivery_penalty_gbp`
  - mark confidence low.

### 8.3 Demand Ceiling (Conversion / Volume Realism) — effective-price first
Demand ceiling is defined in effective-price space:
- `demand_ceiling_effective_gbp`

Translate to landed-price per snapshot:
```text
demand_ceiling_landed_gbp = demand_ceiling_effective_gbp - our_delivery_penalty_gbp
```

### 8.4 Manual Cap (Optional, reason-coded)
```text
final_ceiling_landed_gbp = min(final_ceiling_landed_gbp, manual_cap_price_gbp)
```

### 8.5 Final clamp
```text
final_ceiling_landed_gbp = min(
  compliance_ceiling_landed_gbp,
  eligibility_ceiling_landed_gbp,
  demand_ceiling_landed_gbp,
  manual_cap_price_gbp?
)
hard_floor_price_gbp <= candidate_price_gbp <= final_ceiling_landed_gbp
```

### 8.6 Mode binding (how the same ceilings behave differently)
| Mode | Typical binding ceiling | Why |
|---|---|---|
| `active_competition` | Eligibility | You are constrained by what can win share/BB |
| `low_no_competition` | Demand | You are constrained by customer conversion, not rivals |
| `defensive_hold` | Compliance | Risk-averse behavior, policy safety dominates |

### 8.7 Failure state
If `final_ceiling_landed_gbp < hard_floor_price_gbp`:
- do **not** run optimisation
- escalate with `FAIL_CEILING_BELOW_HARD_FLOOR`

If any ceiling is missing:
- continue only if a safer ceiling exists
- otherwise escalate (`FAIL_NO_SAFE_CEILING`)

---

## 9) Strategy State Machine (Unified)
A **strategy state** determines which engine is allowed to act.

### 9.1 States (canonical set)
- `maximize_profit` (default)
- `low_no_competition` (mandatory when competition is absent)
- `defensive_hold` (risk-minimising)
- `floor_discovery` (bounded experiment)
- `maximize_share` (Supervisor-only)
- `pressure` (manual-only, capital strategy)

### 9.2 State selection rules (high level)
1) If a pressure case is `active` → `state = pressure`
2) Else if competition absent → `state = low_no_competition`
3) Else if volatility / integrity risk high → `state = defensive_hold`
4) Else → `state = maximize_profit`
5) `maximize_share` and `floor_discovery` require Supervisor approval and are time-boxed.

### 9.3 Lane vs State (Portfolio Governor integration)
- If `portfolio_gate_status = fail`:
  - states allowed: `low_no_competition`, `maximize_profit` (restricted), `defensive_hold`
  - states blocked: `pressure`, `floor_discovery`, `maximize_share`
- If `portfolio_gate_status = restricted`:
  - pressure blocked
  - floor discovery restricted to minimal budgets
- Pressure requires:
  - `portfolio_lane = fight`
  - `pressure_allowed_flag = true`
  - Head approval of a pressure case

---

## 10) Pressure State (Nuclear Mode) — Full Integration

### 10.1 What pressure is (strip emotion)
Pressure is:
> A short-term intentional reduction in profit per unit in order to increase long-term expected profit by forcing competitor exit or retreat.

This is **capital allocation**, not routine repricing.

### 10.2 Why it is risky (why we do not automate execution)
Pressure can fail due to:
- fighting the wrong opponent (infinite-capital or structurally-lower-cost sellers)
- CPT/eligibility anchoring risk (you permanently drag the listing’s future ceiling down)
- operational/cashflow strain (higher volume at lower margin)

### 10.3 The only rational case
Pressure is rational only if:

```text
Net_expected_profit_after_exit
>
Profit_during_pressure_period
+
Risk_adjusted_cost
```

Where `Risk_adjusted_cost` includes:
- cashflow strain and stockout risk
- operational load (pick/pack/reorder)
- return/refund exposure
- probability the competitor returns

If you cannot model this, you cannot safely automate pressure.

---

### 10.4 Pressure Qualification Framework (mandatory gates)
A pressure case cannot be approved unless **all** gates pass.

#### Gate 1 — Opponent validation (do not fight structurally stronger sellers)
All must be true (thresholds are configurable, but must be explicit in the case record):
- `seller_persistence_score >= persistence_threshold`
- `seller_reaction_speed <= reaction_speed_max` (must be “fast chaser”)
- `seller_floor_confidence >= floor_confidence_min`
- `seller_capital_depth_score <= capital_depth_max`
- `opponent_type NOT IN {amazon_retail, brand_direct}` unless explicitly approved with special reason code

If opponent is structurally stronger → **disqualify**.

Opponent-type heuristics (starter):
- **amazon_retail**: seller_id indicates Amazon or channel/brand patterns strongly match
- **brand_direct**: consistent lowest cost behaviour + brand ownership signals + high persistence
- **distributor_clearance**: deep cuts with low persistence + short duration + price not reactive
- **low_stock**: price stays fixed, disappears soon after (needs cautious inference; do not assume)

#### Gate 2 — Profit uplift model (expected gain must be > 0)
Compute:
- `expected_post_exit_profit_per_day`
- `expected_pressure_duration_days`
- `pressure_profit_per_day`
- `probability_of_exit`
- `expected_uplift_days`

Then:
```text
margin_loss_per_day = (baseline_profit_per_day - pressure_profit_per_day)

expected_gain =
(probability_of_exit × expected_uplift_days × uplift_profit_per_day)
-
(expected_pressure_duration_days × margin_loss_per_day)
```

Rule:
- if `expected_gain <= 0` → **abort**
- no emotion allowed

#### Gate 3 — Resource check (you must be able to sustain the campaign)
All must be true:
- `stock_days_cover >= required_pressure_days + buffer_days`
- `cash_buffer_gbp >= cash_buffer_min_gbp`
- `operational_capacity_score >= ops_threshold`

If not → abort.

#### Gate 4 — Compliance + CPT anchor distortion check (protect future ceiling)
Pressure must respect:
- `pressure_price_gbp >= hard_floor_price_gbp` (always)
- `pressure_price_gbp >= price_history_anchor_floor_gbp` (new: protects future ceiling)
- `pressure_price_gbp >= compliance_floor_gbp` (if you maintain any additional compliance floor)
- if the campaign would create a new “too-low anchor” relative to recent history → abort unless Head overrides with explicit reason code.

**Price-history anchor floor (recommended)**
Maintain:
- `lowest_landed_price_last_30d_gbp`
- `lowest_landed_price_last_90d_gbp`
- `cpt_last_30d_gbp` trend (daily)

Then define:
```text
price_history_anchor_floor_gbp =
max(
  hard_floor_price_gbp,
  lowest_landed_price_last_30d_gbp - anchor_extension_allowance_gbp
)
```

Purpose:
- allow *small* new lows when justified
- block huge step-downs that permanently reset CPT/eligibility anchors

---

### 10.5 What automation is allowed to do (safe scope)
Automation may:
- detect candidate scenarios (aggressor enters; margin collapse; persistent chasing)
- compute a pressure feasibility score (with assumptions declared)
- generate a recommended plan (time box, floor, max daily cut, exit triggers)
- surface “do not fight” warnings with reason codes

Automation may NOT:
- activate pressure
- write pressure prices
- extend a campaign past expiry

### 10.5.1 What should be automated instead (preferred stable gains)
Pressure is high-variance. The system should bias automation effort toward:
- seller delta learning (effective-price space)
- seller classification + opponent typing
- reaction scoring and persistence scoring
- profit-curve optimisation (argmax profit/day inside floors/ceilings)
- eligibility ceiling detection (signal + market-based)
- defensive holds and volatility kill switches
- low/no-competition margin harvesting toward demand ceiling

These produce stable gains. Pressure produces volatile outcomes and must stay gated.

---

### 10.6 Pressure plan behaviour while active
Once approved:

**Time box**
- default `max_pressure_days = 5`
- hard expiry timestamp is mandatory

**Movement rules**
- hard floor never breached
- `max_daily_cut_gbp` enforced
- cooldown enforced after campaign ends

**Exit triggers (predefined)**
Any of the following triggers ends the campaign:
- competitor stockout/disappearance (offer removed)
- competitor delivery deterioration (their effective price rises vs you)
- competitor price retreat (they stop chasing and move up)
- time expiry

**If expiry hits without exit**
- auto-revert to `defensive_hold`
- no extension without review and a new approval record

---

### 10.7 Post-pressure harvest rule (critical)
If competitor exits/retreats:
1) immediately revert to normal state (`maximize_profit` or `low_no_competition`)
2) re-run ceilings (they may have changed)
3) climb via profit-led ladder toward demand ceiling (do **not** instantly jump to ceiling)
4) monitor for competitor re-entry during the first 72 hours

---

### 10.8 Evidence requirement before any “partial automation”
Pressure execution remains manual until:
- **20–30 completed pressure cases** exist
- a clear majority show positive **net** expected gain vs baseline
- CPT anchor damage rate is acceptably low
- operational load impact is quantified and tolerable

Only then can you consider partial automation (still with hard gates).

---

## 11) Decision Flow Per H-Cycle (Mandatory Order)

### Step 0 — Strategy State Resolution
- If `pressure_case_status = active` → follow pressure plan
- Else choose state using §9 rules

### Step 1 — Portfolio Governor Gate (Mandatory Daily)
Load `portfolio_gate_status` and `portfolio_lane`.

- If `fail`: no duel logic; exploit/ignore behaviour; minimal cadence.
- If `restricted`: narrow ladder, defensive cadence, block pressure.

### Step 2 — Head Boundaries (Hard)
Validate:
- `hard_floor_price_gbp` exists and is sane
- `soft_floor_price_gbp` exists
- inventory constraints (stock days cover)
- state is allowed by gate status

### Step 3 — Market Truth Snapshot (Offer Instances)
Capture all offers (do not collapse to one offer per seller).
Detect:
- Buy Box winner + price
- channels and delivery postures
- new sellers / exits
- coupons/promos
- offer count changes

### Step 4 — Delivery Value Engine Pass
Compute effective price for every offer.

### Step 5 — Ceiling Engine (Snapshot-specific ceilings)
Compute compliance / eligibility / demand ceilings.
Compute final ceiling and binding type.
Log clamp reasons.

### Step 6 — Market-Without-Us Baseline (Mandatory)
Remove our offer and estimate baseline units without us.

### Step 7 — Seller Delta Engine (Effective-price seller game)
Maintain delta bounds and confidence.
Re-enter learning on drift/unknown.

### Step 8 — Seller Priority Behaviour Weighting
Apply seller priority to ladder density, cadence, relearn sensitivity.

### Step 9 — Candidate Ladder Construction (Normal states only)
Build ladder between:
- `hard_floor_price_gbp`
- `final_ceiling_landed_gbp`

Rules:
- larger steps near ceiling
- tighter steps near learned competitor thresholds
- include anchors:
  - ceiling anchor
  - current price
  - hard floor anchor
- obey ladder depth limit (`api_budget_tier`)

### Step 10 — Outcome + Profit Estimation (Normal states only)
For each candidate landed price `P`:
- compute our landed and effective price (using current penalty)
- estimate:
  - win probability vs relevant sellers
  - estimated share
  - confidence score
- compute:
  - `expected_units(P) = baseline_units * estimated_total_share(P)`
  - `profit_per_unit(P) = P - cost_per_unit - fees(P) - expected_refund_impact`
  - `expected_profit_per_day(P) = expected_units(P) * profit_per_unit(P)`

Optimisation rule (default):
- choose `argmax(expected_profit_per_day(P))`

Tie-breakers:
1. higher ROI within band
2. lower volatility risk (higher confidence)
3. lower cadence / API burn

If all candidates are negative profit/day:
- escalate for `defensive_hold` / disengage / clearance review

### Step 11 — Guardrails + Risk Caps
- never breach hard floor
- daily downward movement cap
- cooldown between moves
- max step size
- volatility kill switch
- inventory risk cap
- pressure is manual-only

### Step 12 — Approval + Execution
- normal state: Supervisor approves the move, Executioner writes
- pressure state: Executioner writes per the approved plan schedule

### Step 13 — Observe + Update Learning (If Stable)
Update seller delta, delivery multiplier, demand model only under stability rules.

---

## 12) Portfolio Governor (Mandatory Daily Capital Allocation Gate)
Purpose: prevent low-yield duels and enforce capital discipline.

Daily formula:
```text
listing_worth_fighting_score =
  expected_profit_per_day
  * aggressor_probability
  * capital_lockup_factor
  * delivery_competitiveness_factor
```

Lane actions by threshold:
- below ignore threshold -> `ignore`
- between ignore and exploit -> `exploit`
- between exploit and defend -> `defend`
- above defend -> `fight`

Mandatory outputs:
- `listing_worth_fighting_score`
- `portfolio_lane`
- `portfolio_gate_status`
- `portfolio_reason_code`

Pressure allowance rule (new):
- `pressure_allowed_flag = true` only if:
  - `portfolio_lane = fight`
  - expected profit/day upside is high enough to justify war risk
  - stock/cash/ops buffers are healthy

---

## 13) Seller Priority Behaviour Weight Layer
Priority levels:
- `ignore`, `exploit`, `neutral`, `defend`, `pressure_candidate`

Rules:
- priority affects ladder density, probe sensitivity, cadence, and volatility tolerance
- never bypass floors/ceilings/guardrails
- `pressure_candidate` enables *recommendation generation* only (not execution)

---

## 14) Learning Integrity (Market Structure Safety)

### 14.1 Market Structure Hash (must be recorded for every event)
Hash should include (minimum):
- seller_id set + count
- channels distribution
- coupons/promos flags
- shipping patterns
- fastest delivery days + delivery distribution
- Buy Box holder + price
- timestamp bucket

### 14.2 Update Rules (Hard)
Seller memory updates only if:
- market_structure_hash unchanged during observation window
- promo not suspected
- confidence threshold met

Delivery multiplier updates only if:
- sufficient stable events
- consistent bias evidence
- delivery-learning confidence threshold met

Demand model updates only if:
- sufficient clean data points across price bands
- stable delivery model version
- clearly observed conversion/velocity inflection in effective space

---

## 15) Outputs and Logging Requirements (Minimum Set)

Runtime outputs (must exist):
- `out/h_executioner_action_log.csv`
- `out/h_worker_probe_event_log.csv`
- `out/h_worker_probe_response_log.csv`
- `out/h_seller_profiles.csv`
- `out/h_seller_of_interest.csv`
- `out/h_seller_delta_learning.csv`
- `out/h_delivery_value_events.csv`
- `out/h_sku_delivery_model.csv`
- `out/h_eligibility_intel_daily.csv`
- `out/h_compliance_intel_daily.csv`
- `out/h_demand_model.csv`
- `out/h_ceiling_events.csv`
- `out/h_portfolio_governor_daily.csv`
- `out/h_seller_priority_model.csv`

Pressure-specific outputs (new):
- `out/a_pressure_recommendations_daily.csv`
- `out/h_pressure_case_log.csv`
- `out/h_pressure_actions.csv`
- `out/h_pressure_outcomes.csv`

Every execution must log:
- price facts (our/rival/BB; landed/effective)
- delivery facts (min/max days, fastest days, penalties)
- ceiling facts (compliance/eligibility/demand/final, binding ceiling)
- eligibility facts (FOEP/CPT used, confidence)
- behaviour facts (direction, lag, persistence)
- portfolio facts (score, lane, gate)
- seller priority facts
- decision facts (state, reason codes, confidence, clamps)
- profit facts (estimated profit/day before/after, units/day estimate)

Pressure executions additionally must log:
- `pressure_case_id`
- `plan_day_index`
- `max_daily_cut_gbp` + whether clamp applied
- exit trigger hit (if any)
- CPT/FOEP trend snapshot (to detect anchor distortion)

---

## 16) Rollout Path (Recommended)
### Stage A — Pilot SKU live learning (controlled)
Implement:
- DVE Layer 1 curve
- effective price logging
- seller delta learning in effective space
- ceiling event logging (even if demand ceiling is provisional)

### Stage B — Three-ceiling enforcement (hard)
- compliance ceiling with buffer
- eligibility ceiling (signal + market-based)
- demand ceiling safe-mode proxy
- final ceiling clamp drives ladder construction

### Stage C — Profit-led decision layer (default)
Profit engine becomes default selection rule.

### Stage D — Pressure recommendation only (no execution)
- implement opponent classification + pressure scoring
- generate daily pressure candidates and scorecards
- collect evidence and refine gates
- **no pressure execution automation**

### Stage E — Manual pressure case workflow (time-boxed)
- execute only with Head approval
- log complete pressure cases and outcomes
- target: 20–30 cases before any discussion of partial automation

### Stage F — Eligibility intelligence (A-cycle)
- FOEP + CPT pulls as daily baseline.

### Stage G — Demand ceiling learning (slow)
- enable demand ceiling model in effective-price space with strict stability gating.

### Stage H — DVE learned correction (multiplier)
- enable multiplier learning with strict evidence rules.

### Stage I — Event-driven refresh gate (pre-expansion)
- implement `ANY_OFFER_CHANGED` and `PRICING_HEALTH` listen-first.
- keep low-frequency safety polling fallback.
- no SKU expansion until stable.

---

## 17) Appendix — Reason Codes (Starter Set)

### Objective / State
- `STATE_MAX_PROFIT`
- `STATE_LOW_NO_COMPETITION`
- `STATE_DEFENSIVE_HOLD`
- `STATE_FLOOR_DISCOVERY`
- `STATE_MAX_SHARE`
- `STATE_PRESSURE_MANUAL`

### Pressure gating
- `PRESSURE_CANDIDATE_DETECTED`
- `PRESSURE_GATE_FAIL_OPPONENT_STRONG`
- `PRESSURE_GATE_FAIL_EXPECTED_GAIN_NONPOSITIVE`
- `PRESSURE_GATE_FAIL_RESOURCE`
- `PRESSURE_GATE_FAIL_CPT_ANCHOR_RISK`
- `PRESSURE_APPROVED_HEAD`
- `PRESSURE_ABORTED_KILL_CONDITION`
- `PRESSURE_EXIT_COMPETITOR_STOCKOUT`
- `PRESSURE_EXIT_COMPETITOR_RETREAT`
- `PRESSURE_EXIT_DELIVERY_SHIFT`
- `PRESSURE_EXIT_TIME_EXPIRY`
- `PRESSURE_COOLDOWN_ACTIVE`

### Ceilings
- `CEIL_COMPLIANCE_APPLIED`
- `CEIL_ELIG_SIGNAL_APPLIED`
- `CEIL_ELIG_MARKET_APPLIED`
- `CEIL_DEMAND_APPLIED`
- `CEIL_MANUAL_CAP_APPLIED`
- `CEIL_FINAL_BOUND_COMPLIANCE`
- `CEIL_FINAL_BOUND_ELIGIBILITY`
- `CEIL_FINAL_BOUND_DEMAND`
- `ELIG_CEILING_FOEP_USED`
- `ELIG_CEILING_CPT_USED`
- `ELIG_CEILING_MIN_APPLIED`
- `ELIG_CEILING_OVERRIDDEN_MANUAL`
- `FAIL_CEILING_BELOW_HARD_FLOOR`

### Guardrails / integrity
- `GUARDRAIL_HARD_FLOOR_CLAMP`
- `GUARDRAIL_MAX_STEP_CLAMP`
- `GUARDRAIL_COOLDOWN_BLOCK`
- `MARKET_STRUCTURE_CHANGED_INVALIDATE`
- `WALK_AWAY_LANE_DOWNGRADE`

### Portfolio Governor
- `PORTFOLIO_GOVERNOR_PASS`
- `PORTFOLIO_GOVERNOR_RESTRICTED`
- `PORTFOLIO_GOVERNOR_FAIL`
- `PORTFOLIO_LANE_CHANGED`

### Seller Priority
- `SELLER_PRIORITY_IGNORE`
- `SELLER_PRIORITY_EXPLOIT`
- `SELLER_PRIORITY_NEUTRAL`
- `SELLER_PRIORITY_DEFEND`
- `SELLER_PRIORITY_PRESSURE_CANDIDATE`

### Delivery Value Engine
- `DVE_BASE_CURVE_APPLIED`
- `DVE_MULTIPLIER_APPLIED`
- `DVE_DELIVERY_UNKNOWN_FALLBACK`
- `DVE_MULTIPLIER_UPDATE_BLOCKED_LOW_CONFIDENCE`
- `DVE_MULTIPLIER_UPDATED`

### Learning
- `SELLER_DELTA_DRIFT_RELEARN`
- `SELLER_DELTA_UPDATE_BLOCKED_UNSTABLE_MARKET`
- `DEMAND_MODEL_UPDATE_BLOCKED_LOW_CONFIDENCE`
- `DEMAND_MODEL_UPDATED`
