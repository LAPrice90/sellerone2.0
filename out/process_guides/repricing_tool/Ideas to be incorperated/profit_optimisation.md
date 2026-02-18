Profit Optimisation Layer – Official Decision Logic

Status: Active Design
Date: 2026-02-12
Applies to: H Pricing Cycle (Head → Supervisor → Executioner)

Purpose

Replace “win all sellers” logic with:

Maximise expected profit per day under competitive constraints.

The system must not default to lowest winning price.
The system must choose the price that generates the highest sustainable daily contribution.

Core Principle

Winning the Buy Box is not the objective.

Extracting maximum sustainable profit is the objective.

Decision Order (Mandatory Flow)

For each SKU at each pricing cycle:

Apply boundary constraints (Head)

Generate candidate price ladder

Evaluate expected outcome per candidate

Select price with highest expected profit/day

Pass through guardrails

Execute only if approved

No execution occurs before full evaluation.

Step 1 – Boundaries (Head Layer)

Per SKU the Head defines:

hard_floor_price_gbp
soft_floor_price_gbp
competitive_ceiling_price_gbp
target_roi_band_pct
today_intent
api_budget_tier


All candidate prices must lie within:

hard_floor_price_gbp <= candidate_price <= competitive_ceiling_price_gbp


No exceptions.

Step 2 – Candidate Price Ladder Construction

Build structured ladder between floor and ceiling.

Example:

If:

hard_floor = 7.50
ceiling = 10.99
current_price = 8.94


Construct candidate set:

10.99
10.49
9.99
9.49
8.99
8.69
8.39
7.99
7.69
7.50


Rules:

Use larger steps near ceiling.

Use tighter steps near known competitor floors.

Include all known required_price_to_win_s values from seller games.

Never exceed configured ladder depth.

Step 3 – Seller Game Evaluation Per Candidate

For each candidate price P:

For each relevant seller S:

Compute:

effective_price_ours(P)
effective_price_rival_s
delta_vs_s
win_probability_vs_s


Use:

Learned delta bounds

Delivery penalty model

Seller reaction profile

Seller floor estimate

Promo suspicion flags

Output per seller:

estimated_share_gain_s(P)


Aggregate across sellers:

estimated_total_share(P)

Step 4 – Unit and Profit Estimation

For each candidate P:

Estimate units/day
expected_units_if_competitive(P)
=
baseline_units_from_rank
× estimated_total_share(P)

Estimate unit profit
profit_per_unit(P)
=
P
- cost_per_unit
- fees(P)
- expected_refund_impact

Estimate daily profit
expected_profit_per_day(P)
=
expected_units_if_competitive(P)
× profit_per_unit(P)

Step 5 – Optimisation Rule

Select:

P* = argmax(expected_profit_per_day(P))


If multiple candidates equal:

Prefer:

Higher ROI

Lower volatility risk

Lower required cadence

If all candidates produce negative profit:

Escalate to Supervisor.

Step 6 – Coverage Policy Integration

Seller chess games feed profit model.

They do not dictate final price.

Replace old policy:

coverage_mode = win_all


With:

objective_mode = maximize_profit


Optional override modes (Supervisor only):

maximize_share
defensive_hold
floor_discovery
pressure (manual only)


Default is always maximize_profit.

Step 7 – When Pressure Mode Is Rational

Pressure is allowed only when:

(projected_profit_after_exit
-
profit_during_pressure_window)
> 0


Required fields:

seller_floor_confidence
seller_persistence_score
stock_days_cover
expected_post_exit_roi
pressure_duration_estimate


Pressure must be:

Time-boxed

Hard floor protected

Explicitly reason-coded

Manually approved

Never autonomous.

Step 8 – FBA vs FBM Handling

Channel is not the classification signal.

Seller classification must include:

seller_margin_tolerance_estimate
seller_capital_depth_score
seller_persistence_score
seller_reaction_speed
seller_priority_level


Priority levels:

ignore
exploit
neutral
defend
pressure


Channel (FBA/FBM) only influences delivery delta modelling.

Step 9 – Delivery Value Integration

Effective price is mandatory:

effective_price = landed_price + delivery_penalty


Delivery penalty must be:

Learned per SKU or cluster

Bracket-tested using delta engine

Confidence scored

No global constant allowed.

Step 10 – Market Structure Integrity

Every delta test must record:

market_structure_hash


If during test:

Offer count changes

New seller appears

Delivery posture shifts

Coupon/promo flags change

Then:

Invalidate delta confidence

Do not update learning bounds

Step 11 – Walk Away Logic (Critical)

Add mandatory daily evaluation:

listing_worth_fighting_score
=
expected_profit_per_day
× aggressor_probability
× capital_lockup_factor


If below threshold:

Downgrade SKU lane

Reduce cadence

Avoid duel state

System must be able to disengage.

Step 12 – Output Requirements Per Cycle

Executioner receives:

approved_target_price
reason_codes
confidence_score
expiry_utc
state


Every move must log:

previous_price
new_price
profit_estimate_before
profit_estimate_after
seller_game_summary


No silent decisions.

Step 13 – Guardrails

Mandatory protections:

Never breach hard floor

Cap total daily downward movement

Cooldown between ladder steps

Stop if volatility exceeds threshold

Kill switch enabled globally

Structural Summary

Old Model:
Solve seller games → choose lowest price.

New Model:
Solve seller games → estimate profit curve → choose peak.

This is a profit engine, not a domination engine.

Non-Negotiable Philosophy

Control is not the objective.
Margin is not the objective.
Volume is not the objective.

Sustainable daily contribution is the objective.