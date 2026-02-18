# Masterplan v4 — Unified Repricing Intelligence + Delivery Value Engine + Three-Ceiling Governance

Status: Active Draft (Unified v4)  
Date: 2026-02-12  
Owner: Luke (business intent), Codex (execution support)

## 0) What Changed vs v3.1 (diff guide)
1. **Three-Ceiling Model is now canonical and explicit**
   - **Compliance Ceiling** (policy / suppression safety)
   - **Eligibility Ceiling** (Buy Box feasibility)
   - **Demand Ceiling** (conversion / volume realism)
   - Ceilings are computed and logged separately, then combined into a single `final_ceiling_price_gbp`.
2. **Ceilings are computed in the correct “space”**
   - **Compliance & FOEP/CPT ceilings are “landed-price ceilings”** (Amazon policy / eligibility signals are price-based).
   - **Demand ceiling is defined in “effective-price space”** (price + delivery reality), then translated back to landed price using the Delivery Value Engine.
   - A **DVE-adjusted eligibility ceiling** is added as a *market-based* eligibility bound when FOEP is missing or suspected wrong.
3. **A dedicated “Ceiling Engine” is added to the A-cycle + H-cycle wiring**
   - A-cycle stores the daily ceiling inputs and baseline ceilings.
   - H-cycle recomputes snapshot-specific ceilings using current delivery/competition.
4. **Ceiling binding is mode-aware**
   - Competitive mode: eligibility ceiling usually binds.
   - Low/no competition: demand ceiling usually binds.
   - Defensive mode: compliance ceiling usually binds.
5. **New logging requirement**
   - Every H-cycle produces a `ceiling_event` record with the three ceilings, the binding ceiling, confidence, and clamp reasons.

---

## 1) Canonical Rule (Single Source of Truth)
- This file is the only authoritative repricing plan going forward.
- Any other plan files are reference/archive unless their content is explicitly copied into this file.

---

## 2) Goal
Build a repricing system that:
- **Maximises expected sustainable profit per day** under competitive constraints (default).
- Supports **aggressive tactics** (share capture / pressure / floor discovery) only when rational, never as default.
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
14. **Seller priority is mandatory weighting**: `ignore/exploit/neutral/defend/pressure` must affect cadence and ladder behaviour.

---

## 4) Operating Model (Roles)
### Head (Boundaries + Intent)
Sets per-SKU boundaries and intent **before** any optimisation runs.

Minimum set:
- `hard_floor_price_gbp`
- `soft_floor_price_gbp`
- `target_roi_band_pct`
- `today_intent` (default: `maximize_profit`)
- `api_budget_tier` / cadence limits
- Optional: `manual_cap_price_gbp` (only if explicitly reason-coded)

### Supervisor (Mode + Approval)
Chooses objective mode (default profit; optional overrides).  
Approves ladder depth, max move, cooldown, probe style.  
Approves any aggressive action (manual gate).

### Optimiser (Profit Engine)
Builds candidate ladder within boundaries + ceilings.  
Uses seller-game learning + Delivery Value Engine (effective-price space) to estimate:
- win probabilities / share
- expected units/day
- profit per unit
- expected profit/day per candidate

Recommends the price that maximises expected profit/day subject to constraints.

### Executioner (Write + Observe + Log)
Executes only Supervisor-approved actions.  
Logs action + response windows + measured outcomes.  
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
- market structure fields (see §13)

2) **Persistent Seller Memory Layer (behavioural model)**
Per `SKU + seller_id`:
- `learned_delta_effective_gbp`
- `highest_delta_win_effective_gbp`
- `lowest_delta_loss_effective_gbp`
- `delta_confidence`
- behaviour: `reaction_speed`, `persistence_score`, `capital_depth_score`, `margin_tolerance_estimate`
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
- `external_reference_price_gbp` (optional, if you store/derive it)
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
- `eligibility_ceiling_landed_gbp` (signal-based)
- `eligibility_ceiling_landed_market_gbp` (DVE-adjusted market-based)
- `demand_ceiling_landed_gbp` (derived from effective ceiling minus current DVE penalty)
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

9) **Seller Priority Layer (SKU + seller_id)**
Per `SKU + seller_id`:
- `seller_priority_level` (`ignore`, `exploit`, `neutral`, `defend`, `pressure`)
- `priority_confidence`
- `priority_last_refresh_utc`
- `priority_reason_code`

---

### 5.2 Two Operating Cycles
#### A-Cycle (Daily Intelligence Build) — once/day per SKU
- Pull FOEP + CompetitivePriceThreshold.
- Refresh compliance inputs (external reference price if used; policy buffer).
- Update (or carry forward) demand model state (slow cadence; weekly or when enough data).
- Run Portfolio Governor scoring and lane assignment.
- Refresh seller priority levels from behaviour + economics.
- Compute and store *baseline* ceiling outputs (not snapshot-specific).
- No price writes.

#### H-Cycle (Execution / Optimisation) — event-driven + safety polling fallback
On offer change or scheduled check:
1. snapshot market offers
2. compute effective prices (Delivery Value Engine)
3. compute snapshot-specific ceilings (Ceiling Engine)
4. run profit optimisation in allowed space
5. propose/execute action (approvals + guardrails)
6. log + observe + update learning (if stable)

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
  - market-based eligibility can be computed in effective space and translated to landed space per snapshot

---

## 7) Delivery Value Engine (DVE)

### 7.1 Why it exists
Price-only logic is incomplete: two sellers at the same visible price are not equal if one delivers tomorrow and one delivers in 3 days. Without delivery modelling you:
- misread why sales die when price rises
- overestimate competitiveness at higher prices
- churn price too often and burn margin

DVE converts delivery posture into a monetary penalty used in competitiveness comparisons and optimisation.

### 7.2 Layer 1 — Bootstrap Heuristic (Always On)
Safe baseline (does not require clean learning windows).

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
(when both exist; if only one exists, use that one)

### 7.4 Layer 3 — Learned Correction (Slow Adaptive Adjustment)
Goal: calibrate the “£ per day gap” for each SKU (or SKU-cluster) without overfitting noise.

Parameter:
- `delivery_penalty_multiplier_sku` (default 1.00)
- bounds: 0.50 to 2.00

Update only when ALL are true:
- minimum stable events (`min_delivery_events >= N`, start N=20)
- `market_structure_hash` stable during those events
- promo/coupon not suspected
- consistent undercut bias across time and sellers

Important separation rule:
- seller delta learning updates in effective-price space regardless
- delivery multiplier changes only with broad stable evidence

### 7.5 DVE outputs (must be logged per cycle)
Per offer instance:
- `min_delivery_days`, `max_delivery_days`
- `delivery_gap_days`
- `delivery_penalty_gbp`
- `effective_price_gbp`

Per SKU per cycle:
- `fastest_delivery_days`
- `delivery_penalty_multiplier_sku`
- `delivery_penalty_curve_version`
- `delivery_penalty_unknown_flag`

---

## 8) Three-Ceiling Model (v4 Canonical)

### 8.1 Compliance Ceiling (Policy / Suppression Safety) — landed-price
**Question answered:** “What is the highest landed price we can list without risking suppression / pricing-health enforcement?”

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
- Always on (even if you are the only seller).
- Hard clamp (cannot be overridden autonomously).
- If compliance inputs are missing, mark as low confidence and fall back to:
  - `competitive_price_threshold_gbp` only (if present), else
  - last known compliance ceiling, else
  - escalate (no safe ceiling).

### 8.2 Eligibility Ceiling (Buy Box Feasibility) — landed-price
**Question answered:** “At what landed price can we realistically win/hold the Buy Box given market + our delivery posture?”

Eligibility ceiling has **two independent sources**:

#### A) Signal-based eligibility ceiling (FOEP/CPT)
From A-cycle, landed-price:
```text
eligibility_ceiling_landed_signal_gbp = min(foep_price_gbp, competitive_price_threshold_gbp)
```

#### B) Market-based eligibility ceiling (DVE-adjusted, effective-price game)
This is computed in H-cycle from current offers and seller-game memory:

1) Compute best rival effective price (excluding us):
```text
best_rival_effective_gbp = min(effective_price_gbp_i for all offers i excluding ours)
```

2) Estimate “required effective delta” to win, from learned memory:
```text
required_undercut_effective_gbp = f(learned_delta_effective_gbp, confidence, seller mix)
```

3) Compute our max *effective* price to win:
```text
max_winning_effective_gbp = best_rival_effective_gbp - required_undercut_effective_gbp
```

4) Translate to landed-price via our delivery penalty for this snapshot:
```text
eligibility_ceiling_landed_market_gbp = max_winning_effective_gbp - our_delivery_penalty_gbp
```

Notes:
- If our delivery penalty increases (we’re slower), the landed eligibility ceiling drops automatically.
- If we are the fastest offer (penalty = 0), eligibility ceiling rises (if rivals are slower).

#### Combining signal and market eligibility
Final eligibility ceiling:
```text
eligibility_ceiling_landed_gbp =
  min(eligibility_ceiling_landed_signal_gbp?, eligibility_ceiling_landed_market_gbp?)
```

Rules:
- In **active competition mode**, eligibility ceiling is usually binding.
- In **low/no competition mode**, eligibility ceiling is advisory unless FOEP/CPT confidence is high and you are seeing Buy Box loss above it.

Fallbacks when FOEP is missing:
- Use market-based eligibility ceiling (preferred).
- If market-based cannot be computed (no rivals / insufficient learning):
  - fallback to historical highest winning effective price:
    - `eligibility_ceiling_landed ≈ highest_winning_effective_gbp - our_delivery_penalty_gbp`
  - mark confidence low.

### 8.3 Demand Ceiling (Conversion / Volume Realism) — effective-price first
**Question answered:** “Even if we’re compliant and eligible, where does demand fall off sharply?”

Demand ceiling must be defined in **effective-price space** to include delivery reality.

#### Demand ceiling definition
- `demand_ceiling_effective_gbp`: max effective price before unit/session or velocity collapses.

Learning inputs (slow cadence):
- historical effective price vs unit_session_percent
- historical effective price vs sales velocity
- rank elasticity
- “exit and re-entry” memory (how long sales take to recover after overpricing)

Safe-mode proxy (until model is mature):
- `demand_ceiling_effective_gbp = bbp_max_sold_price_gbp + our_delivery_penalty_at_time_of_sale_gbp` (approx)
- or a manually maintained “max sold price” translated into effective space

#### Translating demand ceiling to landed price (snapshot-specific)
Once H-cycle computes our current delivery penalty:
```text
demand_ceiling_landed_gbp = demand_ceiling_effective_gbp - our_delivery_penalty_gbp
```

This is the key unification:
- When we are slower today, demand ceiling (landed) drops automatically.
- When we are faster, demand ceiling (landed) rises automatically.

Rules:
- Demand ceiling is usually binding in **low/no competition margin expansion**.
- Demand ceiling should be treated as **advisory** if confidence is low.

### 8.4 Manual Cap (Optional, reason-coded)
Manual cap is an additional clamp:
- only set by Head/Supervisor
- must be reason-coded
- always applied as:
```text
final_ceiling_landed_gbp = min(final_ceiling_landed_gbp, manual_cap_price_gbp)
```

### 8.5 Mandatory clamp order
Ceilings clamp in this order (conceptually), but the *final* ceiling is their minimum:

```text
final_ceiling_landed_gbp = min(
  compliance_ceiling_landed_gbp,
  eligibility_ceiling_landed_gbp,
  demand_ceiling_landed_gbp,
  manual_cap_price_gbp?
)
```

Then:
```text
hard_floor_price_gbp <= candidate_price_gbp <= final_ceiling_landed_gbp
```

### 8.6 Mode binding (how the same ceilings behave differently)
| Mode | Typical binding ceiling | Why |
|---|---|---|
| `active_competition` | Eligibility | You’re constrained by what can win share/BB |
| `low_no_competition` | Demand | You’re constrained by customer conversion, not rivals |
| `defensive_hold` | Compliance | Risk-averse behaviour, policy safety dominates |

### 8.7 Failure states
If `final_ceiling_landed_gbp < hard_floor_price_gbp`:
- do **not** run optimisation
- escalate with reason:
  - `FAIL_CEILING_BELOW_HARD_FLOOR`
- recommend lane downgrade or listing exit.

If any ceiling is missing:
- continue only if a safer ceiling exists; otherwise escalate.

---

## 9) Decision Flow Per H-Cycle (Mandatory Order)
No execution occurs until full evaluation completes.

### Step 0 — Portfolio Governor Gate (Mandatory Daily State)
Load `portfolio_gate_status` and `portfolio_lane`.

- If `fail`: no duel logic; exploit/ignore behaviour; minimal cadence.
- If `restricted`: narrow ladder, defensive cadence, block pressure.

### Step 1 — Head Boundaries (Hard)
Validate:
- `hard_floor_price_gbp` exists and is sane
- `soft_floor_price_gbp` exists
- inventory constraints (stock days cover)
- objective mode is allowed

### Step 2 — Market Truth Snapshot (Offer Instances)
Capture all offers (do not collapse to one offer per seller).
Detect:
- Buy Box winner + price
- channels and delivery postures
- new sellers / exits
- coupons/promos
- offer count changes

### Step 3 — Delivery Value Engine Pass
Compute effective price for every offer.

### Step 4 — Ceiling Engine (Snapshot-specific ceilings)
Compute:
- compliance ceiling (from A-cycle values; apply buffer)
- eligibility ceiling:
  - signal-based from A-cycle
  - market-based from current effective-price competition
- demand ceiling:
  - demand_ceiling_effective from Demand Model
  - translate to landed via our current penalty
- final ceiling = min(all)
Log binding ceiling + clamp reasons.

### Step 5 — Market-Without-Us Baseline (Mandatory)
Before candidate evaluation:
1. remove our offer
2. recalc best rival effective structure
3. estimate `baseline_units_without_us`
4. use baseline for share estimation

### Step 6 — Seller Delta Engine (Effective-price seller game)
Maintain per `SKU + seller_id`:
- `highest_delta_win_effective_gbp`
- `lowest_delta_loss_effective_gbp`
- `learned_delta_effective_gbp`
- `delta_confidence`
- behaviour scores

If drift/unknown:
- re-enter learning (probe sequence)

If market structure changes during probe:
- do not update bounds; reduce confidence

### Step 7 — Seller Priority Behaviour Weighting
Apply `seller_priority_level` to ladder density, cadence, relearn sensitivity.
Never bypass floors/ceilings/guardrails.

### Step 8 — Candidate Price Ladder Construction
Build ladder between:
- `hard_floor_price_gbp`
and
- `final_ceiling_landed_gbp`

Rules:
- larger steps near ceiling
- tighter steps near learned competitor thresholds
- include anchors:
  - ceiling anchor
  - current price
  - hard floor anchor
- obey ladder depth limit (`api_budget_tier`)

### Step 9 — Outcome Estimation Per Candidate (Effective-price game)
For each candidate landed price **P**:
- compute our landed and effective price (using current penalty)
- estimate:
  - win probability vs relevant sellers
  - estimated share
  - confidence score

### Step 10 — Profit Estimation Per Candidate
For each candidate **P**:
- `expected_units(P) = baseline_units * estimated_total_share(P)`
- `profit_per_unit(P) = P - cost_per_unit - fees(P) - expected_refund_impact`
- `expected_profit_per_day(P) = expected_units(P) * profit_per_unit(P)`

### Step 11 — Optimisation Rule (Default)
Select:
- `P* = argmax(expected_profit_per_day(P))`

Tie-breakers:
1. higher ROI within band
2. lower volatility risk (higher confidence)
3. lower cadence / API burn

If all candidates are negative profit/day:
- escalate for defensive hold / disengage / clearance.

### Step 12 — Guardrails + Risk Caps (Mandatory)
- never breach hard floor
- daily downward movement cap
- cooldown between moves
- max step size
- volatility kill switch
- inventory risk cap
- pressure mode manual-only

### Step 13 — Approval + Execution
Supervisor approves exact move.
Executioner writes price and logs:
- price facts (ours/rivals; landed/effective)
- DVE facts (fastest days, our gap, penalty)
- ceiling facts (three ceilings + binding type)
- eligibility facts (FOEP/CPT used? confidence)
- behaviour facts (seller responses, lag)
- portfolio facts (lane/gate)
- seller priority facts
- decision facts (mode, reason codes, confidence)
- profit facts (profit/day before/after)

### Step 14 — Observe + Update Learning (If Stable)
Observe response windows.
Update:
- seller delta memory (effective space) if stable
- delivery multiplier only if strict rules met
- demand model only on slow cadence with clean evidence

---

## 10) Objective Modes and When They Are Allowed
### Default: `maximize_profit`
Profit engine selects peak profit/day candidate.
All ceilings enforced.

### Supervisor-only overrides
#### A) `maximize_share`
Ranking defence / launch where share worth > near-term profit.

#### B) `defensive_hold`
Volatile market or stock constrained:
- narrow ladder
- low cadence
- compliance ceiling as strong clamp

#### C) `floor_discovery`
Experiment:
- fixed budget (moves/time)
- market hash checks
- confidence updates only when stable

#### D) `pressure` (manual only, time-boxed)
Allowed only when expected post-exit profit outweighs pressure losses.
Always:
- reason-coded
- time-boxed
- kill conditions
- hard floor protected

#### E) `low_no_competition` (mandatory state)
Trigger:
- offer_count_without_us <= 1
- OR no rival effective price within proximity band

Behaviour:
- margin-focused upward stepping toward demand ceiling
- monitor aggressor re-entry continuously
- if competitive seller re-enters proximity band: abort stepping, rebuild ladder

---

## 11) Portfolio Governor (Mandatory Daily Capital Allocation Gate)
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
- below ignore threshold → `ignore`
- between ignore and exploit → `exploit`
- between exploit and defend → `defend`
- above defend → `fight`

Mandatory outputs:
- `listing_worth_fighting_score`
- `portfolio_lane`
- `portfolio_gate_status`
- `portfolio_reason_code`

---

## 12) Seller Priority Behaviour Weight Layer
Priority levels:
- `ignore`, `exploit`, `neutral`, `defend`, `pressure`

Integration rules:
- priority affects ladder density, probes, relearn sensitivity, volatility tolerance
- never bypass floors/ceilings/guardrails
- `pressure` priority enables manual escalation candidate only

---

## 13) Learning Integrity (Market Structure Safety)

### 13.1 Market Structure Hash (must be recorded for every event)
Hash should include (minimum):
- seller_id set + count
- channels distribution
- coupons/promos flags
- shipping patterns
- fastest delivery days + delivery distribution
- Buy Box holder + price
- timestamp bucket

### 13.2 Update Rules (Hard)
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
- stable delivery model version (avoid double-learning)
- clearly observed conversion/velocity inflection in effective space

---

## 14) Outputs and Logging Requirements (Minimum Set)
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
- `out/h_ceiling_events.csv`  ← **new in v4**
- `out/h_portfolio_governor_daily.csv`
- `out/h_seller_priority_model.csv`

Every execution must log:
- price facts (our/rival/BB; landed/effective)
- delivery facts (min/max days, fastest days, penalties)
- ceiling facts (compliance/eligibility/demand/final, binding ceiling)
- eligibility facts (FOEP/CPT ceiling, confidence)
- behaviour facts (direction, lag, persistence)
- portfolio facts (score, lane, gate)
- seller priority facts
- decision facts (mode, reason codes, confidence, clamps)
- profit facts (estimated profit/day before/after, units/day estimate)

---

## 15) Rollout Path (Recommended)
### Stage A — Pilot SKU live learning (controlled)
Implement:
- DVE Layer 1 curve
- effective price logging
- seller delta learning in effective space
- ceiling event logging (even if demand ceiling is provisional)

Exit when:
- stable learning records
- no guardrail breaches
- consistent reason-coded actions

### Stage B — Three-ceiling enforcement (hard)
- compliance ceiling with buffer
- eligibility ceiling (signal + market-based)
- demand ceiling safe-mode proxy
- final ceiling clamp drives ladder construction

### Stage C — Profit-led decision layer (default)
Profit engine becomes default selection rule.

### Stage D — Eligibility intelligence (A-cycle)
FOEP + CPT pulls as daily baseline.

### Stage E — Demand ceiling learning (slow)
Enable demand ceiling model in effective space with strict stability gating.

### Stage F — DVE Learned Correction (multiplier)
Enable multiplier learning with strict evidence rules.

### Stage G — Event-driven refresh gate (pre-expansion)
Implement `ANY_OFFER_CHANGED` and `PRICING_HEALTH` listen-first.
Keep low-frequency safety polling fallback.
No SKU expansion until stable.

---

## 16) Appendix — Reason Codes (Starter Set)

### Objective
- `OBJ_MAX_PROFIT`
- `OBJ_MAX_SHARE`
- `OBJ_DEFENSIVE_HOLD`
- `OBJ_FLOOR_DISCOVERY`
- `OBJ_PRESSURE_MANUAL`
- `OBJ_LOW_NO_COMPETITION`

### Ceilings
- `CEIL_COMPLIANCE_APPLIED`
- `CEIL_ELIG_SIGNAL_APPLIED`
- `CEIL_ELIG_MARKET_APPLIED`
- `CEIL_DEMAND_APPLIED`
- `CEIL_MANUAL_CAP_APPLIED`
- `CEIL_FINAL_BOUND_COMPLIANCE`
- `CEIL_FINAL_BOUND_ELIGIBILITY`
- `CEIL_FINAL_BOUND_DEMAND`
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

### Eligibility
- `ELIG_CEILING_FOEP_USED`
- `ELIG_CEILING_CPT_USED`
- `ELIG_CEILING_MIN_APPLIED`
- `ELIG_CEILING_OVERRIDDEN_MANUAL`

### Learning
- `SELLER_DELTA_DRIFT_RELEARN`
- `SELLER_DELTA_UPDATE_BLOCKED_UNSTABLE_MARKET`
- `DEMAND_MODEL_UPDATE_BLOCKED_LOW_CONFIDENCE`
- `DEMAND_MODEL_UPDATED`
