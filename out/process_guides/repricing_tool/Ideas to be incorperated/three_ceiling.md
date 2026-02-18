Good. This is one of the most important structural corrections in your entire system.

Right now “ceiling” in your plan is doing too many jobs. If you don’t split it, your engine will behave inconsistently depending on state, and you won’t know why.

We’re going to formalise the three ceilings properly and show:

What each one protects

How each one makes money

How each one is calculated

How they interact automatically in the H cycle

Why this prevents silent profit erosion and account risk

This integrates directly into your Master Plan architecture 

Codex Master Working Plan - Com…

 and your H-cycle manager stack 

Repricing Manager Stack Plan - …

.

The Three-Ceiling Model

You need three completely separate upper bounds:

Compliance Ceiling

Eligibility Ceiling

Demand Ceiling

Each ceiling answers a different question.

If you collapse them into one number, you will:

Overprice and lose Buy Box

Underprice and leave money on the table

Or risk suppression/account health

1️⃣ Compliance Ceiling
(Policy / External Benchmark Protection)
What It Is

The maximum price you can safely list without risking:

Buy Box removal

Listing suppression

Account health warnings

“Price too high” flags

Loss of featured offer eligibility

This is tied to:

CompetitivePriceThreshold (external retail benchmark)

Amazon’s pricing fairness policies

This ceiling exists even if you are the only seller.

Why It Makes You Money

Because suppression is catastrophic.

A suppressed listing:

Has 0 Buy Box

Lower visibility

Lower conversion

Lower organic rank

Possible account-level consequences

One suppressed SKU can wipe out more profit than any duel win.

Compliance ceiling is your insurance layer.

How It’s Calculated

Inputs:

competitive_price_threshold_gbp
external_reference_price_gbp
policy_buffer_pct


Calculation example:

compliance_ceiling = min(
    competitive_price_threshold_gbp,
    external_reference_price_gbp
) × (1 - policy_buffer_pct)


You add a buffer (e.g. 2–5%) to avoid sitting exactly on the edge.

If CPT is £24.99
Your buffer 3%

Compliance ceiling ≈ £24.24

Automatic Enforcement

This ceiling is applied first in the clamp order.

No candidate price can exceed this.

Ever.

Even in low competition mode.

2️⃣ Eligibility Ceiling
(Buy Box Feasibility Bound)
What It Is

The highest price at which you can realistically win the Buy Box.

This is NOT the same as compliance.

This is tactical.

It depends on:

FOEP

Current competitive structure

Fulfilment posture

Seller metrics

Delivery performance

You can be compliant but still ineligible for Buy Box.

Why It Makes You Money

Because pricing above eligibility ceiling:

Reduces share sharply

Breaks your profit estimation model

Causes “mystery sales collapse”

Triggers unnecessary downward panic moves

If you price at £19.99 but FOEP implies Buy Box only works at £17.99, your profit curve is fantasy.

Eligibility ceiling keeps your optimisation realistic.

How It’s Calculated

Daily A-side pull:

foep_price_gbp
competitive_price_threshold_gbp


Logic:

eligibility_candidate = foep_price_gbp
eligibility_ceiling = min(
    eligibility_candidate,
    competitive_price_threshold_gbp
)


If FOEP missing:

Fallback:

Historical highest winning price

Recent buy box win thresholds

Conservative relative margin above best rival effective price

Confidence must be tracked.

Automatic Use

In active competition mode:

Profit curve ladder is truncated at eligibility_ceiling.

This prevents chasing fantasy margin.

3️⃣ Demand Ceiling
(Market Realism Ceiling)
What It Is

The maximum price customers will actually pay in practice.

Even if:

You are alone

You are compliant

You are Buy Box eligible

Customers may simply not convert at that price.

Demand ceiling answers:

“Where does volume fall off sharply?”

Why It Makes You Money

Because low/no competition mode is where real margin is made.

If you underprice when alone, you lose silent profit.

If you overprice beyond demand ceiling, you kill volume.

This ceiling defines the peak of your profit curve when competition is weak.

How It’s Calculated

Inputs:

Historical price vs unit_session_percent

Historical price vs sales velocity

Rank elasticity

BBP max sold price (temporary)

Exit and re-entry baseline memory 

Codex Master Working Plan - Com…

Example approach:

Identify historical price bands

Measure conversion drop

Fit simplified curve

Detect inflection point

Temporary implementation (safe mode):

demand_ceiling = manually maintained BBP max sold price


Flag as provisional.

Clamp Order – Mandatory Hierarchy

This is critical.

Ceilings must clamp in this order:

final_ceiling =
min(
    compliance_ceiling,
    eligibility_ceiling,
    demand_ceiling
)


Then:

hard_floor <= candidate_price <= final_ceiling

Why Order Matters
Active Competition Mode

Eligibility ceiling dominates.

You care about:

Winning share

Tactical realism

Demand ceiling is secondary because you’re constrained by rivals anyway.

Low/No Competition Mode

Demand ceiling dominates.

You care about:

Extracting maximum realistic margin

Edge upward gradually

Eligibility ceiling becomes less relevant if no real rivals.

Compliance ceiling always active.

How This Helps Profitability

Without split ceilings:

You might:

Price to demand ceiling

But exceed eligibility ceiling

Lose Buy Box silently

Drop price aggressively

Trigger duel

Destroy margin

Or:

Price above compliance ceiling

Get suppressed

Lose listing

Damage account

Or:

Use eligibility ceiling when alone

Leave 20% margin untapped

Three ceilings prevent all three failure modes.

Automatic Integration Into Profit Engine

Inside H Cycle:

Step 1 – A-Cycle Refresh (Daily)

Store:

compliance_ceiling
eligibility_ceiling
demand_ceiling
confidence_scores

Step 2 – Profit Optimisation Layer

When building candidate ladder:

upper_bound = final_ceiling


Generate ladder between hard_floor and upper_bound.

Step 3 – Mode Weighting

Supervisor sets mode:

mode = active_competition | low_competition | defensive


Mode influences weight:

Active → eligibility ceiling binding

Low competition → demand ceiling binding

Defensive → compliance ceiling binding (risk-averse)

Step 4 – Execution

Executioner never sees raw FOEP or CPT.

Executioner only sees:

approved_target_price
clamped_upper_bound
reason_codes

Risk Reduction Impact

This model:

Prevents suppression risk

Prevents silent Buy Box loss

Prevents overpricing fantasies

Prevents underpricing in monopoly moments

Stabilises profit curve estimation

Reduces unnecessary cadence

Less volatility = more predictable daily profit.

Structural Summary

One ceiling = confused logic.

Three ceilings = layered constraint system.

Each ceiling protects a different failure domain:

Ceiling	Protects Against
Compliance	Policy & suppression
Eligibility	Tactical infeasibility
Demand	Overpricing & lost volume

Together they create:

A bounded optimisation space.

And bounded optimisation is what makes automation safe.