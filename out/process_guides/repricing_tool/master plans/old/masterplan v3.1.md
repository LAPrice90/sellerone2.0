# Masterplan v3.1 - Unified Repricing Intelligence + Delivery Value Engine (Strategic Controls Restored)

Status: Active Draft (Unified v3.1)
Date: 2026-02-12
Owner: Luke (business intent), Codex (execution support)

## 0) What Changed vs v2 (so you can diff quickly)
1. **Delivery Value Engine is now first-class**, not a short section:
   - Always-on **bootstrap delivery penalty curve** (safe baseline).
   - **Eligibility overlay (FOEP + CompetitivePriceThreshold)** as a ceiling constraint + diagnostic.
   - **Slow learned correction** via per-SKU delivery multiplier (prevents overfitting).
2. **Effective price is computed for every offer instance**, not just “ours”:
   - `effective_price_offer = landed_price_offer + delivery_penalty_offer`
3. **Seller delta learning and delivery learning are separated**:
   - Seller delta learns Buy Box / rotation behaviour **in effective-price space**.
   - Delivery multiplier learns “£ per day gap” calibration **only with strong evidence**.
4. Added explicit **A-cycle (daily eligibility intelligence)** + **H-cycle (execution)** wiring.
5. Restored **Portfolio Governor** as a mandatory daily capital-allocation gate.
6. Restored **Seller Priority Taxonomy** as a behaviour-weight layer for optimisation and escalation.

### Quick logic mapping (v2/v3 -> v3.1)
| Legacy logic block | Present in v3.1 | Where in v3.1 |
|---|---|---|
| Profit-led default (`maximize_profit`) | Yes | Section 10 |
| Market-Without-Us baseline | Yes | Section 8, Step 4 |
| Ceiling precedence model | Yes | Section 9 |
| Manual-only pressure mode | Yes | Section 10.D |
| Walk away / lane downgrade logic | Yes | Section 11 |
| Seller priority behaviour weighting | Yes | Section 12 |
| Delivery value in effective-price space | Yes | Sections 6 and 7 |
| A-cycle and H-cycle wiring | Yes | Section 5.2 |

---

## 1) Canonical Rule (Single Source of Truth)
- This file is the only authoritative repricing plan going forward.
- Any other plan files are reference/archive unless their content is explicitly copied into this file.

---

## 2) Goal
Build a repricing system that:
- **Maximises expected sustainable profit per day** under competitive constraints (default).
- Still supports **aggressive tactics** (share capture / pressure / floor discovery) when rational, but **never as default**.
- Learns from **real Buy Box outcomes** and **seller behaviour**, not just visible “lowest price”.
- Properly prices the economic reality that:
  - **Delivery speed has monetary value**
  - **Eligibility signals (FOEP/CPT) constrain what can win**
- Scales from one pilot SKU to broad coverage with strict guardrails and explainability.

---

## 3) Non-Negotiables
1. **Default objective is profit optimisation**: never “lowest winning price” by default.
2. **Hard floor is sacred**: never breached, for any mode.
3. **Effective price is mandatory**: competition comparisons use effective price, not visible price.
4. **Strategy unit is `SKU + seller_id`**: learning and behaviour are seller-specific.
5. **Learning is behaviour-triggered**: re-enter learning on drift/unknowns; calendar checks are only backup.
6. **Market structure integrity**: if market changes during a test, learning confidence must be invalidated.
7. **Execution must be explainable**: reason codes + confidence + logged pre/post estimates.
8. **Aggression is an explicit override**: gated, time-boxed, measurable, with kill conditions.
9. **Eligibility intelligence never writes prices**: FOEP/CPT constrain or warn; they do not set price targets.
10. **No “delivery = stock” inference**: delivery windows are treated as competitiveness signals only.
11. **Portfolio Governor is mandatory daily**: SKUs must pass a fight-worthiness gate before high-cadence tactics.
12. **Seller priority is mandatory weighting**: `ignore/exploit/neutral/defend/pressure` must affect cadence and ladder behaviour.

---

## 4) Operating Model (Roles)
### Head (Boundaries + Intent)
Sets per-SKU boundaries and intent **before** any optimisation runs. Owns risk budget and “where we fight”.

Head sets (minimum set):
- `hard_floor_price_gbp`
- `soft_floor_price_gbp`
- `target_roi_band_pct`
- `today_intent` (default: `maximize_profit`)
- `api_budget_tier` / cadence limits
- Optional: `manual_cap_price_gbp` (only if explicitly reason-coded)

### Supervisor (Mode + Approval)
Chooses tactical objective mode (default profit; optional overrides).
Approves the action envelope: ladder depth, max move, cooldown, probe style.
Approves any aggressive action (manual gate).

### Optimiser (Profit Engine)
Builds candidate price ladder within boundaries + ceilings.
Uses seller-game learning + delivery penalties to estimate:
- win probabilities / share
- expected units/day
- profit per unit
- expected profit/day per candidate

Recommends the price that maximises expected profit/day subject to constraints.

### Executioner (Write + Observe + Log)
Executes only Supervisor-approved action.
Logs action, response windows, and measured outcomes.
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

5) **Portfolio Governor Layer (SKU-level, daily)**
Per `SKU`:
- `listing_worth_fighting_score`
- `aggressor_probability`
- `capital_lockup_factor`
- `delivery_competitiveness_factor`
- `portfolio_lane` (`fight`, `defend`, `exploit`, `ignore`)
- `portfolio_gate_status` (`pass`, `restricted`, `fail`)

6) **Seller Priority Layer (SKU + seller_id)**
Per `SKU + seller_id`:
- `seller_priority_level` (`ignore`, `exploit`, `neutral`, `defend`, `pressure`)
- `priority_confidence`
- `priority_last_refresh_utc`
- `priority_reason_code`

### 5.2 Two Operating Cycles
#### A-Cycle (Daily Intelligence Build) — once/day per SKU
- Pull FOEP + CompetitivePriceThreshold.
- Store into Eligibility Intelligence Layer.
- Run Portfolio Governor scoring and lane assignment.
- Refresh seller priority levels from behaviour + economics.
- No price writes.
- Produces eligibility, portfolio, and priority inputs for H-cycle.

#### H-Cycle (Execution / Optimisation) — event-driven + safety polling fallback
- On offer change or scheduled check:
  - snapshot market offers
  - compute effective prices (Delivery Value Engine)
  - run profit optimisation
  - propose or execute action (with approvals + guardrails)
  - log + observe + update learning (if stable)

---

## 6) Core Definitions (Canonical)
- `landed_price_gbp = listing_price_gbp + shipping_gbp`
- `fastest_delivery_days = min(offer.min_delivery_days for offers in snapshot)`
- For any offer **i**:
  - `delivery_gap_days_i = offer_i.min_delivery_days - fastest_delivery_days`
  - `delivery_penalty_gbp_i = DVE_penalty(delivery_gap_days_i) * delivery_penalty_multiplier_sku`
  - `effective_price_gbp_i = landed_price_gbp_i + delivery_penalty_gbp_i`

Notes:
- Delivery penalty is **non-negative** and is **0** for the fastest offer(s).
- If delivery cannot be determined reliably, set `delivery_penalty_unknown_flag = true` and use conservative fallback (see §7.4).

---

## 7) Delivery Value Engine (DVE)

### 7.1 Why it exists
Price-only logic is incomplete: two sellers at the same visible price are not equal if one delivers tomorrow and one delivers in 3 days. Without delivery modelling you:
- misread why sales die when price rises
- overestimate competitiveness at higher prices
- churn price too often and burn margin

DVE converts delivery posture into a monetary penalty that can be used inside profit optimisation.

### 7.2 Layer 1 — Bootstrap Heuristic (Always On)
This is the safe baseline that does not require “clean” learning windows.

**Default conservative curve (v0):**
- gap 0 days → £0.00
- gap 1 day  → £0.15
- gap 2 days → £0.30
- gap 3 days → £0.45
- gap 4+ days → £0.60 (cap)

Implementation rule:
- `gap = clamp_int(delivery_gap_days, min=0, max=4)`
- `penalty_base = [0.00, 0.15, 0.30, 0.45, 0.60][gap]`

This prevents catastrophic mispricing when you are slower.

### 7.3 Layer 2 — Eligibility Signal Overlay (FOEP + CPT)
Eligibility signals do not write prices. They act as:
1) **Ceiling constraints** (don’t waste probes above eligibility reality)
2) **Diagnostics** (warn when your model is structurally misaligned)

Store daily:
- `foep_price_gbp`
- `competitive_price_threshold_gbp`
- `eligibility_confidence`

Compute:
- `buy_box_eligibility_ceiling_gbp = min(foep_price_gbp, competitive_price_threshold_gbp)` (when both exist)
- If only one exists, use that one.
- If neither exists, `eligibility_ceiling = null` (system continues using market realism ceiling).

How H-cycle uses eligibility ceiling:
- In competitive modes, **exclude** candidate prices above the eligibility ceiling unless Supervisor explicitly overrides with reason code.
- In low/no-competition margin stepping, treat eligibility ceiling as **advisory** (you can step above, but you must monitor Buy Box loss and revert quickly).

### 7.4 Layer 3 — Learned Correction (Slow Adaptive Adjustment)
Goal: calibrate the “£ per day gap” for each SKU (or SKU-cluster) without overfitting noise.

Parameter:
- `delivery_penalty_multiplier_sku` (default 1.00)
- Bounds (recommended): 0.50 to 2.00

Update only when ALL are true:
- minimum number of stable events achieved (`min_delivery_events >= N`, pick N=20 as starting point)
- market_structure_hash stable during those events
- promo/coupon not suspected
- observed “required undercut” bias is consistent across time and sellers

What triggers an update:
- If you repeatedly must undercut more than predicted (in effective-price space), increase multiplier.
- If you repeatedly win at higher deltas than predicted, decrease multiplier.

Important separation rule:
- Seller delta learning is updated in effective-price space regardless.
- Delivery multiplier is adjusted only when there is broad, stable evidence that the penalty curve is mis-scaled.

### 7.5 DVE Outputs (must be logged per cycle)
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

## 8) Decision Flow Per H-Cycle (Mandatory Order)
No execution occurs until the full evaluation completes.

### Step 0 - Portfolio Governor Gate (Mandatory Daily State)
Load latest `portfolio_gate_status` and `portfolio_lane` before H-cycle tactics.

If `portfolio_gate_status = fail`:
- do not enter competitive duel logic
- apply exploit/ignore lane behaviour
- reduce cadence tier
- disable pressure mode

If `portfolio_gate_status = restricted`:
- narrow ladder depth
- keep defensive cadence
- block pressure unless explicit Supervisor exception

### Step 1 — Boundaries (Head)
Validate:
- `hard_floor_price_gbp <= candidate_price <= absolute_ceiling_price_gbp`

Where absolute ceiling is derived via §9.2 (ceiling precedence).

### Step 2 — Market Truth Snapshot (Offer Instances)
Capture all offers (do not collapse to one offer per seller).
Detect:
- Buy Box winner, channel, delivery posture
- new sellers, seller exits
- coupons/promos
- offer count changes

### Step 3 — Delivery Value Engine Pass
Compute:
- `fastest_delivery_days`
- `effective_price_gbp_i` for every offer i

All competitiveness comparisons from this point use effective prices.

### Step 4 — Market-Without-Us Baseline (Mandatory)
Before candidate evaluation:
1. Remove our offer from the offer set.
2. Recalculate best effective offer structure.
3. Estimate `baseline_units_without_us`.
4. Use this baseline for share estimation.

Profit modelling must always compare:
- `expected_units_if_competitive(P)`
vs
- `baseline_units_without_us`

No optimisation is valid without this baseline.

### Step 5 — Learning / Memory (Seller Delta Engine)
Per `SKU + seller_id`, maintain:
- `highest_delta_win_effective_gbp`
- `lowest_delta_loss_effective_gbp`
- `learned_delta_effective_gbp`
- `delta_confidence`
- seller behaviour scores

If drift is detected or delta is unknown:
- re-enter learning immediately (probe sequence)

If market structure changes during probe:
- do not update learning bounds; reduce confidence

### Step 5b - Seller Priority Behaviour Weighting
Apply `seller_priority_level` to how optimisation runs (not to replace optimisation):
- `ignore`: wider ladder spacing, low cadence, no pressure path
- `exploit`: increase upward margin bias, slower downward reactions
- `neutral`: standard rules
- `defend`: tighter ladder around competitor thresholds, faster re-entry checks
- `pressure`: manual override path only, never autonomous

### Step 6 — Candidate Price Ladder Construction
Build structured ladder between:
- `hard_floor_price_gbp`
and
- `ceiling_price_gbp` (after applying ceiling precedence §9.2)

Rules:
- larger steps near ceiling
- tighter steps near learned competitor thresholds
- include all known “required price to win vs seller S” points
- never exceed ladder depth (per `api_budget_tier`)
- include anchors:
  - ceiling anchor
  - current price
  - hard floor anchor

### Step 7 — Outcome Estimation Per Candidate (Effective-Price Seller Game)
For each candidate **P**:
- compute `our_landed_price(P)` and `our_effective_price(P)` (with current delivery posture)
- for each relevant seller **S**:
  - compare `our_effective_price(P)` to `rival_effective_price_s`
  - use learned deltas + seller profile to estimate:
    - `win_probability_vs_s(P)`
    - `estimated_share_gain_s(P)`
- aggregate:
  - `estimated_total_share(P)`
  - `confidence_score(P)` (learning certainty + market stability + delivery certainty)

### Step 8 — Profit Estimation Per Candidate
For each candidate **P**:
- `expected_units(P) = baseline_units_from_rank * estimated_total_share(P)`
- `profit_per_unit(P) = P - cost_per_unit - fees(P) - expected_refund_impact`
- `expected_profit_per_day(P) = expected_units(P) * profit_per_unit(P)`

### Step 9 — Optimisation Rule (Default)
Select:
- `P* = argmax(expected_profit_per_day(P))`

Tie-breakers (in order):
1. Higher ROI (within target ROI band)
2. Lower volatility risk (higher confidence, fewer expected reactions)
3. Lower cadence / API burn

If all candidates yield negative expected profit/day:
- escalate to Supervisor for:
  - defensive hold
  - disengage / lane downgrade
  - stock clearance (if applicable)

### Step 10 — Guardrails + Risk Caps
Mandatory protections:
- never breach hard floor
- daily downward movement cap
- cooldown between moves
- max step size
- volatility kill switch (stop if market unstable / reaction storm)
- inventory risk cap (no fight mode when stock_days_cover low unless clearance intent)

### Step 11 — Approval + Execution
Supervisor approves exact move (or rejects).
Executioner writes price and logs:
- previous/new price
- profit estimate before/after
- seller-game summary
- DVE summary (fastest days, our gap, penalties)
- reason codes
- confidence score
- expiry_utc

Executioner then observes response windows and records outcomes.

---

## 9) Ceiling Model (Precedence Order)
Ceiling is not “a number you feel good about”. It is computed with strict precedence:

1. **Policy/compliance ceiling (hard)**
2. **Eligibility ceiling (FOEP/CPT)** when available (confidence-scored)
3. **Market realism ceiling** (competitive + conversion realities)
4. **Manual cap** (only if explicitly reason-coded)

Output:
- `ceiling_price_gbp` (final applied)
- `ceiling_reason_code` + confidence

---

## 10) Objective Modes and When They Are Allowed
### Default: `maximize_profit`
- Profit engine selects the peak profit/day candidate.
- Delivery value and eligibility constraints are enforced.

### Supervisor-only overrides (non-default systems)
#### A) `maximize_share`
Use when ranking defence / launch makes share worth more than near-term profit.
- Hard floor still applies.
- Must set explicit share target or max acceptable profit sacrifice.

#### B) `defensive_hold`
Use when market is volatile or stock constrained.
- Narrow ladder, low cadence, stability first.
- Eligibility ceiling used as stronger clamp.

#### C) `floor_discovery`
Use when seller floor confidence is low but worth learning.
- Treated as an experiment:
  - fixed budget (max moves, max time)
  - market_structure_hash checks
  - confidence updates only when stable

#### D) `pressure` (manual only, time-boxed)
Use only when:
`(projected_profit_after_exit - profit_during_pressure_window) > 0`

Required before approval:
- seller_floor_confidence
- seller_persistence_score
- stock_days_cover
- expected_post_exit_roi
- pressure_duration_estimate
- kill conditions (stop after X hours if no retreat)

Hard rules:
- never autonomous
- always reason-coded
- always time-boxed
- hard floor protected

#### E) `low_no_competition` (mandatory state)
Trigger:
- offer_count_without_us <= 1
- OR no competitive seller within delta proximity band (effective-price space)

Behaviour:
1. Enter margin-focused lane.
2. Step upward using structured ladder:
   - larger steps near ceiling
   - cooldown enforced
3. Monitor aggressor re-entry continuously.

Immediate re-entry trigger:
If a new competitive seller appears OR rival effective price enters proximity band:
- abort upward stepping
- rebuild ladder
- re-enter competitive optimisation mode

---

## 11) Portfolio Governor (Mandatory Daily Capital Allocation Gate)
Purpose: prevent low-yield SKU duels and enforce capital discipline before H-cycle tactics.

Daily formula:
`listing_worth_fighting_score = expected_profit_per_day * aggressor_probability * capital_lockup_factor * delivery_competitiveness_factor`

Where:
- `expected_profit_per_day`: expected sustainable profit at current tactical lane
- `aggressor_probability`: likelihood of active rival reaction/duel state
- `capital_lockup_factor`: penalty for slow stock turns and working-capital drag
- `delivery_competitiveness_factor`: penalty when our delivery posture is structurally weak

Lane actions by threshold:
- Below `ignore_threshold`: set lane to `ignore`, reduce cadence to minimum, block pressure
- Between `ignore_threshold` and `exploit_threshold`: set lane to `exploit`, margin-led steps only
- Between `exploit_threshold` and `defend_threshold`: set lane to `defend`, controlled competitive cadence
- Above `defend_threshold`: allow `fight` lane, full optimisation cadence

Mandatory outputs:
- `listing_worth_fighting_score`
- `portfolio_lane`
- `portfolio_gate_status`
- `portfolio_reason_code`

---

## 12) Seller Priority Behaviour Weight Layer
Purpose: classify seller importance so optimisation effort matches economic reality.

Priority levels:
- `ignore`
- `exploit`
- `neutral`
- `defend`
- `pressure`

Integration rules:
- Priority affects ladder density, probe aggressiveness, relearn sensitivity, and volatility tolerance.
- Priority never bypasses hard floor, ceiling, or guardrail protections.
- `pressure` priority enables a manual path only; it does not auto-authorise pressure mode.

Minimum mapping:
- `ignore`: low cadence, wide ladder, minimal probes
- `exploit`: margin expansion bias, opportunistic raises
- `neutral`: baseline behaviour
- `defend`: tighter ladder, faster response, higher watch sensitivity
- `pressure`: manual-only escalation candidate with strict kill conditions

---

## 13) Learning Integrity (Market Structure Safety)

### 13.1 Market Structure Hash (must be recorded for every event)
Hash should include (minimum):
- seller_id set + count
- channels (FBA/FBM/Amazon) distribution
- coupons/promos flags
- shipping price patterns
- `fastest_delivery_days` + distribution of min delivery days
- Buy Box holder + price
- timestamp bucket

### 13.2 Update Rules (Hard)
Offer data updates seller memory only if:
- `market_structure_hash` unchanged during the observation window
- `promo_suspected_flag = false`
- confidence threshold met

Delivery multiplier updates only if:
- sufficient stable events
- consistent bias evidence
- explicit delivery-learning confidence threshold met

---

## 14) Outputs and Logging Requirements (Minimum Set)
Runtime outputs (must exist):
- `out/h_executioner_action_log.csv`
- `out/h_worker_probe_event_log.csv`
- `out/h_worker_probe_response_log.csv`
- `out/h_seller_profiles.csv`
- `out/h_seller_of_interest.csv`
- `out/h_seller_delta_learning.csv`
- `out/h_delivery_value_events.csv` (new: per cycle offer delivery + penalties)
- `out/h_sku_delivery_model.csv` (new: multiplier + confidence over time)
- `out/h_eligibility_intel_daily.csv` (new: FOEP/CPT pulls + confidence)
- `out/h_portfolio_governor_daily.csv` (new: score, lane, gate status)
- `out/h_seller_priority_model.csv` (new: priority level + confidence)

Every execution must log:
- price facts (our, rival, buy box, landed, effective)
- delivery facts (min/max days, fastest days, penalties)
- eligibility facts (FOEP/CPT ceiling, confidence)
- behaviour facts (direction, lag, persistence)
- portfolio facts (fighting score, lane, gate status)
- seller priority facts (level, confidence, reason code)
- decision facts (mode, reason codes, confidence, guardrail clamps)
- profit facts (estimated profit/day before/after, units/day estimate)

---

## 15) Rollout Path (Recommended)
### Stage A — Pilot SKU live learning (controlled)
- SKU: `JB-RGB6-LZOJ`
- Implement:
  - DVE Layer 1 curve
  - effective price logging
  - seller delta learning in effective space
- Exit when:
  - stable learning records
  - no guardrail breaches
  - consistent reason-coded actions

### Stage B — Profit-led decision layer (default)
- Profit engine becomes default selection rule.
- Seller games inform share estimation; do not dictate final price.

### Stage C — Eligibility intelligence (A-cycle)
- Add FOEP + CompetitivePriceThreshold pulls.
- Use as eligibility ceiling (constraint + diagnostic).

### Stage D — DVE Learned Correction (multiplier)
- Enable SKU-level multiplier learning with strict stability rules.

### Stage E — Event-driven refresh gate (pre-expansion)
- Implement `ANY_OFFER_CHANGED` and `PRICING_HEALTH` in listen-first mode.
- Use push events for targeted refresh checks.
- Keep low-frequency safety polling fallback.
- No SKU expansion until Stage E gate passes.

### Stage F — Portfolio and priority hardening
- Enforce daily Portfolio Governor thresholds in production.
- Enforce seller priority weighting in H-cycle ladder + cadence controls.
- Add drift alerts for lane flips and priority instability.

---

## 16) Appendix — Reason Codes (Starter Set)
Objective:
- `OBJ_MAX_PROFIT`
- `OBJ_MAX_SHARE`
- `OBJ_DEFENSIVE_HOLD`
- `OBJ_FLOOR_DISCOVERY`
- `OBJ_PRESSURE_MANUAL`
- `OBJ_LOW_NO_COMPETITION`

Guardrails / integrity:
- `GUARDRAIL_HARD_FLOOR_CLAMP`
- `GUARDRAIL_MAX_STEP_CLAMP`
- `GUARDRAIL_COOLDOWN_BLOCK`
- `MARKET_STRUCTURE_CHANGED_INVALIDATE`
- `WALK_AWAY_LANE_DOWNGRADE`

Portfolio Governor:
- `PORTFOLIO_GOVERNOR_PASS`
- `PORTFOLIO_GOVERNOR_RESTRICTED`
- `PORTFOLIO_GOVERNOR_FAIL`
- `PORTFOLIO_LANE_CHANGED`

Seller Priority:
- `SELLER_PRIORITY_IGNORE`
- `SELLER_PRIORITY_EXPLOIT`
- `SELLER_PRIORITY_NEUTRAL`
- `SELLER_PRIORITY_DEFEND`
- `SELLER_PRIORITY_PRESSURE_CANDIDATE`

Delivery Value Engine:
- `DVE_BASE_CURVE_APPLIED`
- `DVE_MULTIPLIER_APPLIED`
- `DVE_DELIVERY_UNKNOWN_FALLBACK`
- `DVE_MULTIPLIER_UPDATE_BLOCKED_LOW_CONFIDENCE`
- `DVE_MULTIPLIER_UPDATED`

Eligibility:
- `ELIG_CEILING_FOEP_USED`
- `ELIG_CEILING_CPT_USED`
- `ELIG_CEILING_MIN_APPLIED`
- `ELIG_CEILING_OVERRIDDEN_MANUAL`

Learning:
- `SELLER_DELTA_DRIFT_RELEARN`
- `SELLER_DELTA_UPDATE_BLOCKED_UNSTABLE_MARKET`
