# Masterplan v2 - Repricing Intelligence (Profit-Led Default, Aggression As A Controlled Override)

Status: Active Draft (Consolidated)
Date: 2026-02-12
Owner: Luke (business intent), Codex (execution support)

## 1) Canonical Rule (Single Source of Truth)
- This file is the only authoritative repricing plan going forward.
- Any other plan files are reference/archive unless their content is explicitly copied into this file.

## 2) Goal
Build a repricing system that:
- **Maximises expected sustainable profit per day** under competitive constraints (default).
- **Can still deploy aggressive tactics** (share capture / pressure / floor discovery) when they are rational, but **never as the default**.
- Learns from **real Buy Box outcomes** and **seller behaviour**, not just visible lowest prices.
- Scales safely from **one pilot SKU** to full SKU coverage with strict guardrails and explainability.

## 3) Non-Negotiables
1. **Default objective is profit optimisation**: never "lowest winning price" by default.
2. **Hard floor is sacred**: never breached, for any mode.
3. **Effective price is mandatory**: landed price + delivery penalty (delivery value is part of competition).
4. **Strategy unit is `SKU + seller_id`**: learning and behaviour are seller-specific.
5. **Learning is behaviour-triggered**: re-enter learning on drift/unknowns; calendar checks are only a backup.
6. **Market structure integrity**: if the market changes during a test, learning confidence must be invalidated.
7. **Execution must be explainable**: reason codes + confidence + logged pre/post estimates.
8. **Aggression is an explicit override**: gated, time-boxed, and measurable (with kill conditions).

## 4) System Roles (Operating Model)
### Head (Boundaries + Intent)
- Sets per-SKU boundaries and intent **before** any optimisation runs.
- Owns risk budget and "where we fight / where we disengage".
- Does **not** execute price writes.

Head sets (minimum set):
- `hard_floor_price_gbp`
- `soft_floor_price_gbp`
- `competitive_ceiling_price_gbp` (computed ceiling, not arbitrary)
- `target_roi_band_pct`
- `today_intent` (default: maximize_profit)
- `api_budget_tier` / cadence limits

### Supervisor (Mode + Approval)
- Chooses tactical state and objective mode (default profit, optional overrides).
- Approves the action envelope: ladder depth, max move, cooldown, probe style.
- Approves **any aggressive / pressure action** (manual gate).

### Optimiser (Profit Engine)
- Builds candidate price ladder within boundaries.
- Uses seller-game learning + delivery penalties to estimate:
  - win probabilities / share
  - expected units/day
  - profit per unit
  - expected profit/day per candidate
- Recommends the price that maximises expected profit/day subject to constraints.

### Executioner (Write + Observe + Log)
- Executes only the Supervisor-approved action.
- Logs action, response windows, and measured outcomes.
- Updates learning memory **only when market structure is stable** and confidence rules allow.

## 5) Decision Flow Per Pricing Cycle (Mandatory Order)
No execution occurs until the full evaluation completes.

1) **Boundaries (Head)**
- Validate:
  `hard_floor_price_gbp <= candidate_price <= competitive_ceiling_price_gbp`
- Set objective mode default unless override explicitly set.

2) **Market Truth Snapshot**
- Capture all offers (do not collapse to one offer per seller).
- Detect:
  - Buy Box winner, channel, delivery posture
  - new sellers, seller exits, coupons/promos
  - offer count changes

### Mandatory Market-Without-Us Baseline
Before candidate evaluation:
1. Remove our offer from the offer set.
2. Recalculate Buy Box winner and effective structure.
3. Estimate `baseline_units_without_us`.
4. Use this baseline as reference for share estimation.

Profit modelling must always compare:
- `expected_units_if_competitive(P)`
- `baseline_units_without_us`

No optimisation is valid without this baseline.

3) **Learning / Memory (Seller Delta Engine)**
- For each `SKU + seller_id`, maintain:
  - `highest_delta_win_gbp`
  - `lowest_delta_loss_gbp`
  - `learned_delta_gbp`
  - `delta_confidence`
  - `promo_suspected_flag`
  - seller behaviour: `reaction_speed`, `persistence_score`, `capital_depth_score`, `margin_tolerance_estimate`
- If drift is detected or delta is unknown:
  - re-enter learning immediately (probe sequence)
- If market structure changes during probe:
  - do **not** update learning bounds; reduce confidence.

### Data Separation Requirement
Two independent data layers must exist:

1) **Offer Instance Layer (event level)**
- raw offer snapshot
- landed price
- delivery window
- channel
- promo flag
- timestamp

2) **Seller Memory Layer (persistent behavioural model)**
- `learned_delta_gbp`
- `highest_delta_win_gbp`
- `lowest_delta_loss_gbp`
- `seller_floor_estimate`
- `reaction_speed_score`
- `persistence_score`
- `margin_tolerance_estimate`
- `delta_confidence`

Offer data updates seller memory only if:
- `market_structure_hash` unchanged
- `promo_suspected_flag = false`
- confidence threshold met

4) **Candidate Price Ladder Construction**
- Build structured ladder between hard floor and competitive ceiling.
- Rules:
  - Larger steps near ceiling
  - Tighter steps near known competitor floors / learned deltas
  - Include all known "required price to win vs seller S" candidate points
  - Never exceed configured ladder depth (per `api_budget_tier`)
- Ladder must include:
  - ceiling anchor
  - current price
  - "close-in" points around learned competitor thresholds
  - hard floor anchor

5) **Outcome Estimation Per Candidate (Seller Game -> Share)**
For each candidate price **P**:
- For each relevant seller **S**:
  - Compute `effective_price_ours(P)`
  - Compare to `effective_price_rival_s`
  - Use learned deltas + delivery penalty + seller profile to estimate:
    - `win_probability_vs_s(P)`
    - `estimated_share_gain_s(P)`
- Aggregate:
  - `estimated_total_share(P)`
  - confidence score (based on learning certainty + market stability)

6) **Profit Estimation Per Candidate**
For each candidate **P**:
- Estimate units/day:
  - `expected_units(P) = baseline_units_from_rank * estimated_total_share(P)`
- Compute profit per unit:
  - `profit_per_unit(P) = P - cost_per_unit - fees(P) - expected_refund_impact`
- Compute expected profit/day:
  - `expected_profit_per_day(P) = expected_units(P) * profit_per_unit(P)`

7) **Optimisation Rule (Default)**
Select:
- `P* = argmax(expected_profit_per_day(P))`

Tie-breakers (in order):
1. Higher ROI (within the target ROI band)
2. Lower volatility risk (higher confidence, fewer expected reactions)
3. Lower required cadence / API burn

If **all** candidates yield negative expected profit/day:
- Escalate to Supervisor for:
  - defensive hold
  - disengage / lane downgrade
  - stock clearance logic (if applicable)

8) **Guardrails + Risk Caps**
Apply mandatory protections:
- Never breach hard floor
- Daily downward movement cap
- Cooldown between moves
- Max step size
- Volatility kill switch (stop if market unstable / reaction storm)
- Inventory risk cap (no "fight" mode when stock_days_cover is low unless explicit clearance intent)

9) **Approval + Execution**
- Supervisor approves the exact move (or rejects).
- Executioner writes price and logs:
  - `previous_price`, `new_price`
  - `profit_estimate_before`, `profit_estimate_after`
  - `seller_game_summary`
  - `reason_codes`
  - `confidence_score`
  - `expiry_utc`
- Executioner then observes response windows and records outcomes.

## 6) Objective Modes and When They Are Allowed
### Default mode: `maximize_profit` (always-on unless overridden)
- Uses the profit engine.
- May still compete, but only to the point the profit curve justifies.

### Optional override modes (Supervisor-only)
These are "non-default systems" you keep available for specific moments.

#### A) `maximize_share`
Use when:
- strategic share is worth more than near-term profit (e.g., ranking defence, launch phase)
Constraints:
- Hard floor still applies.
- Must set explicit share target or maximum acceptable profit sacrifice.

#### B) `defensive_hold`
Use when:
- market is too volatile to trust estimates, or stock is constrained.
Constraints:
- Narrow ladder, low cadence, stability first.

#### C) `floor_discovery`
Use when:
- seller floor confidence is low but worth learning.
Constraints:
- Treated as an experiment:
  - fixed budget (max moves, max time)
  - mandatory market_structure_hash checks
  - confidence updates only when stable.

#### D) `pressure` (manual only, time-boxed)
Use only when:
- The net expected gain is positive:

  `(projected_profit_after_exit - profit_during_pressure_window) > 0`

Required fields before approval:
- `seller_floor_confidence`
- `seller_persistence_score`
- `stock_days_cover`
- `expected_post_exit_roi`
- `pressure_duration_estimate`
- kill conditions (e.g., "stop after X hours if no seller retreat")

Hard rules:
- Never autonomous
- Always reason-coded
- Always time-boxed
- Hard floor protected

### E) `low_no_competition` (mandatory state)
Trigger:
- `offer_count_without_us <= 1`
- OR no competitive seller within delta proximity band

Behaviour:
1. Enter margin-focused lane.
2. Step upward using structured ladder:
   - larger steps near ceiling
   - cooldown enforced between increases
3. Monitor aggressor re-entry continuously.

Re-entry Trigger (Immediate Switch):
If new competitive seller appears OR if rival `effective_price` is within proximity band:
- abort upward stepping
- rebuild ladder
- re-enter competitive optimisation mode

No delay permitted on re-entry.

## 7) Walk Away Logic (Mandatory Daily Evaluation)
Each SKU must compute daily:

`listing_worth_fighting_score =
 expected_profit_per_day
 * aggressor_probability
 * capital_lockup_factor`

If below threshold:
- downgrade SKU lane (fight -> defend -> exploit -> ignore)
- reduce cadence
- avoid duel state by default

The system must be able to disengage and preserve capital.

## 8) Seller Classification (Beyond FBA vs FBM)
Seller "priority level" is based on behaviour and economics, not channel.

Maintain per seller:
- `seller_margin_tolerance_estimate`
- `seller_capital_depth_score`
- `seller_persistence_score`
- `seller_reaction_speed`
- `seller_priority_level`

Priority levels:
- `ignore`
- `exploit`
- `neutral`
- `defend`
- `pressure`

Channel (FBA/FBM) influences delivery penalty only.

## 9) Delivery Value Integration
- Always compute effective price:
  `effective_price = landed_price + delivery_penalty`
- Delivery penalty must be:
  - learned per SKU (or SKU-cluster)
  - bracket-tested using the delta engine
  - confidence-scored
- No global constant delivery penalty.

## 10) Market Structure Integrity (Learning Safety)
Every delta test must record:
- `market_structure_hash`

If during a probe/test:
- offer count changes
- new seller appears
- delivery posture shifts
- coupon/promo flags change

Then:
- invalidate delta confidence for that event
- do not update learning bounds from that data

## 11) Outputs and Logging Requirements (Minimum Set)
Runtime outputs (must exist):
- `out/h_executioner_action_log.csv`
- `out/h_worker_probe_event_log.csv`
- `out/h_worker_probe_response_log.csv`
- `out/h_seller_profiles.csv`
- `out/h_seller_of_interest.csv`
- `out/h_seller_delta_learning.csv`

Every execution must log:
- price facts (our, rival, buy box, landed, effective)
- delivery facts (min/max days, prime, channel)
- behaviour facts (direction, lag, persistence)
- decision facts (mode, reason codes, confidence, guardrail clamps)
- profit facts (estimated profit/day before/after, units/day estimate)

## 12) Rollout Path
### Stage A - Pilot SKU live learning (controlled)
- SKU: `JB-RGB6-LZOJ`
- Objective:
  - stable learning records
  - no guardrail breaches
  - consistent reason-coded actions
- Exit criteria:
  - repeatable learned deltas with confidence
  - market structure checks working
  - profit engine producing stable recommendations

### Stage B - Profit-led decision layer (becomes default)
- Profit engine becomes the default selection rule.
- Seller games feed share estimation; do not dictate final price.

### Stage C - Eligibility intelligence (ceiling quality)
- Add FOEP and CompetitivePriceThreshold (when available) as ceiling inputs.
- Store in Product DB for ceiling guidance and reason codes.

### Stage D - Event-driven refresh gate (pre-expansion)
- Implement `ANY_OFFER_CHANGED` and `PRICING_HEALTH` in listen-first mode.
- Use push events to trigger targeted refresh checks.
- Keep low-frequency safety polling fallback.
- No SKU expansion until Stage D gate passes.

## 13) Decisions Locked (Resolves D1-D5)
D1 - Final price objective:
- Default = `maximize_profit` (expected profit/day peak).
- Overrides allowed only via Supervisor.

D2 - Learning trigger basis:
- Primary = behaviour-triggered on drift/unknown delta.
- Daily check = backup safety only.

D3 - Pressure automation level:
- Pressure = manual approval only (never autonomous).

D4 - Canonical planner file policy:
- This file is the only authoritative plan.

D5 - Ceiling model precedence (strict order):
1. Policy/compliance ceiling (hard)
2. Eligibility ceiling (FOEP/CPT when available)
3. Market realism ceiling (competitive + conversion realities)
4. Manual cap (only if explicitly reason-coded)

## 14) Appendix - Reason Codes (Starter Set)
- `OBJ_MAX_PROFIT`
- `OBJ_MAX_SHARE`
- `OBJ_DEFENSIVE_HOLD`
- `OBJ_FLOOR_DISCOVERY`
- `OBJ_PRESSURE_MANUAL`
- `GUARDRAIL_HARD_FLOOR_CLAMP`
- `GUARDRAIL_MAX_STEP_CLAMP`
- `GUARDRAIL_COOLDOWN_BLOCK`
- `MARKET_STRUCTURE_CHANGED_INVALIDATE`
- `DELIVERY_PENALTY_LOW_CONFIDENCE`
- `SELLER_DELTA_DRIFT_RELEARN`
- `WALK_AWAY_LANE_DOWNGRADE`



