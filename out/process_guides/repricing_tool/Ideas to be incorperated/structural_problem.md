Good. This one looks technical, but it directly affects profit.

If you get identity wrong at the data layer, your:

Seller floor estimates become noisy

Reaction speed modelling becomes wrong

Delivery value learning becomes polluted

Aggressor classification becomes unstable

Profit curve predictions drift

You don’t just lose analytical clarity — you lose money.

Let’s break this down properly.

The Structural Problem

You correctly said:

Never dedupe by seller_id only.
Store each row as a distinct offer instance. 

Codex Master Working Plan - Com…

Correct.

But your current uniqueness key includes:

landed_price_gbp

min_delivery_days

max_delivery_days

That means:

When price changes → new identity.
When delivery shifts → new identity.

So the system cannot tell whether:

The same offer just repriced

Or the seller changed fulfilment route

Or the seller launched a separate offer configuration

Everything becomes a new “thing”.

That destroys continuity.

Why This Hurts Profit

Because your entire engine depends on behavioural modelling.

You are trying to learn:

Seller floors

Reaction lag

Aggression score

Delivery posture patterns

Win/loss delta

If identity resets on every price change:

Reaction speed appears inconsistent

Floor detection becomes noisy

Delivery value modelling becomes corrupted

Seller classification oscillates

And noisy models lead to overreaction pricing.

Overreaction pricing = margin bleed.

The Correct Structure: Two IDs

We split identity into two layers.

1️⃣ offer_snapshot_id

This represents:

A single observed row at a specific timestamp.

Uniqueness:

timestamp + sku + seller_id + random_tie_break


Every observation row gets one.

This preserves raw truth.

2️⃣ offer_variant_id

This represents:

A stable behavioural entity.

Uniqueness should include:

seller_id_canonical

fulfilment_channel (FBA / FBM)

condition

shipping template

possibly region/marketplace

It must NOT include:

price

delivery days (if dynamic SLA)

It represents:

The structural version of the offer.

So:

If seller changes price → same variant.
If seller changes fulfilment FBA→FBM → new variant.
If seller launches separate FBM and FBA listing → two variants.

Now we can do clean time series.

Why This Improves Profit

Because now you can correctly measure:

1️⃣ Reaction Speed
reaction_lag_minutes =
time(variant reprices after our move)


Previously, price change created new ID → impossible to measure continuity.

Now you can compute:

Average lag

Distribution of lag

Variance of lag

This directly feeds aggression scoring.

Better aggression scoring → better duel avoidance → more stable profit.

2️⃣ Floor Stability

You can track:

lowest_price_reached_by_variant
frequency_of_stop_chasing
floor_confidence_score


If identity resets on each price change, floor detection becomes fragmented.

With stable variant ID:

You see full price descent curve over time.

Better floor estimate → fewer unnecessary undercuts → higher ROI.

3️⃣ Delivery Posture Tracking

If variant keeps same fulfilment but delivery days fluctuate:

You can detect:

SLA instability

Stock pressure

Region variation

If delivery shift creates new identity, this signal disappears.

Delivery modelling improves → effective pricing improves → profit curve improves.

4️⃣ Win Rate Attribution

You can calculate:

variant_win_rate_when_active


This lets you answer:

Does this specific configuration ever truly win?

Or is it noise?

That helps you decide which sellers matter.

Ignoring noise sellers prevents unnecessary price drops.

Automatic Logic Application

Inside H Cycle:

Step 1 – Snapshot Collection

For each pull:

Create:

offer_snapshot_id


Store full raw row.

Step 2 – Variant Mapping

Generate:

offer_variant_id =
hash(
    seller_id_canonical,
    fulfilment_channel,
    condition,
    shipping_template
)


Do NOT include price.

Link snapshot to variant.

Step 3 – Behavioural Aggregation

All behavioural modelling operates on variant level:

reaction_speed_estimate

seller_floor_estimate

seller_aggression_score

delivery_stability_score

win_probability_estimate

Snapshots feed variants.

Variants feed seller profile.

Seller profile feeds pricing engine.

How This Improves the Profit Optimisation Layer

Your profit engine evaluates:

expected_units_if_competitive(P)


This depends on:

Who actually reacts

Who actually fights

Who actually matters

With correct variant continuity:

Reaction modelling stabilises

Aggressor detection stabilises

Delta learning stabilises

Share estimation improves

More accurate share estimation → more accurate profit curve → better price selection.

Better price selection → higher daily contribution.

Structural Improvement in Your Master Plan

Under:

Offer instance handling rules 

Codex Master Working Plan - Com…

Add:

Dual Identity Model (New Mandatory Structure)

Two identifiers must exist:

offer_snapshot_id

Unique per observation row

Includes timestamp

offer_variant_id

Stable across price changes

Includes structural attributes only

Excludes dynamic price and delivery days

All behavioural modelling must operate on offer_variant_id.

Snapshot rows are never deleted or deduplicated.

Why This Is Safer Operationally

It prevents:

Phantom aggressor detection

False volatility spikes

Artificial floor shifts

Delivery penalty mislearning

Erratic cadence escalation

Erratic cadence → more API calls → more price churn → more instability.

Stable identity → stable model → stable profit.

Deeper Profit Angle

Bad identity = noisy data
Noisy data = overfitting
Overfitting = aggressive repricing
Aggressive repricing = margin destruction

Clean identity → smooth signals → controlled pricing → predictable contribution.

Brutal Reality

If you don’t fix this:

Your system will constantly think:

“Seller behaviour changed.”

When actually:

“Seller just repriced.”

You’ll misclassify.

And misclassification drives unnecessary war.

Final Summary

You were right not to dedupe by seller.

But you need structural continuity.

Two IDs:

Snapshot = truth record

Variant = behavioural entity

Snapshots feed variants.
Variants feed seller profiles.
Seller profiles feed profit engine.

And the profit engine feeds your business.