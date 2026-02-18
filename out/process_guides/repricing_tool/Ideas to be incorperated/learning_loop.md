Good. This is one of the most dangerous silent failure points in your entire system.

Your delta learning engine is structurally strong:

* Find first win
* Find first loss
* Narrow bracket
* Store highest_delta_win / lowest_delta_loss
* Re-test daily

That logic is solid.

The problem is not the algorithm.

The problem is **what counts as a valid observation**.

If your learner updates on contaminated outcomes, it will confidently learn the wrong thing — and wrong confidence is far more dangerous than low confidence.

Let’s formalise this properly.

---

# The Core Problem

Your delta engine assumes:

> If we change price and Buy Box outcome changes, the cause is price.

That assumption is false in many cases.

Buy Box can change because of:

* Rotation among equal sellers
* Region-specific delivery differences
* Temporary fulfilment advantage
* Seller metrics (late dispatch rate, ODR)
* Amazon Retail intervention
* Suppression or pricing health flags
* Coupon / hidden discount
* Competitor stock depletion
* Offer count change

If you update delta bounds when one of those occurred, you teach the system nonsense.

And nonsense learning leads to:

* Over-aggressive undercutting
* Phantom delivery penalties
* False aggressor classification
* Margin bleed

---

# The Missing Layer: Outcome Truth Filter

You need a formal layer between:

> Observation
> and
> Learning update

We call this:

## Outcome Admissibility Layer

A delta test result is not automatically “truth”.

It must pass context validation.

---

# New Principle

You already have:

> Data first, thresholds later. 

You now need:

> Outcome quality before learning.

Learning must be conditional.

---

# Context Invariants (Mandatory Checks)

Before a delta update is accepted, the following must be true:

---

## 1️⃣ Competitor Set Stability

Between:

* delta_test_start_timestamp
* delta_test_end_timestamp

Check:

```
offer_count_delta <= allowed_threshold
no new Seller of Interest appeared
no core competitor disappeared
```

If major drift:

Result = contaminated.

---

## 2️⃣ No Listing Suppression

Check:

```
buy_box_suppressed_flag == false
```

If suppressed during test:

Discard result.

---

## 3️⃣ No Self Stockout

Check:

```
our_stock_available > minimum_threshold
```

If we went out of stock mid-test:

Discard result.

Stock distortions destroy delta accuracy.

---

## 4️⃣ No Major Delivery Shift

Check:

```
abs(our_delivery_days_delta) <= allowed_shift
abs(rival_delivery_days_delta) <= allowed_shift
```

If delivery posture changes materially:

Delta invalid.

---

## 5️⃣ No Pricing Health / Eligibility Event

Check:

```
pricing_health_alert == false
eligibility_status_change == false
```

If CPT/FOEP disqualification occurred:

Delta invalid.

---

# How This Improves Profit

Without this layer:

* You “learn” that you need -£0.30 delta
* When actually Buy Box rotated
* You then permanently undercut by £0.30
* That costs margin on every sale

Over a year that’s thousands.

With invariants:

* Only high-quality tests adjust delta
* Delta converges slower but cleaner
* Profit curve becomes stable
* Less unnecessary undercutting

Stability = sustainable daily contribution.

---

# Weighting Instead of Binary Reject

Not all contamination is binary.

Add:

```
context_quality_score ∈ [0,1]
```

If:

* Minor competitor drift → 0.7 weight
* Moderate drift → 0.4 weight
* Major drift → 0 weight

Update rule:

```
new_delta =
old_delta × (1 - learning_rate × quality_score)
+
observed_delta × (learning_rate × quality_score)
```

Low-quality data has low impact.

This prevents one bad event from wrecking your bracket.

---

# Automatic Application in H Cycle

Flow inside Executioner probe:

1. Execute price move.
2. Wait test window.
3. Capture snapshot.
4. Compute invariants.
5. Compute context_quality_score.
6. If quality_score == 0:

   * Log event.
   * Do not update bounds.
7. If quality_score > 0:

   * Update highest_delta_win / lowest_delta_loss with weight.

No direct learning from raw win/loss.

---

# Add Market Structure Hash

To simplify invariant checking:

At delta_test_start:

Compute:

```
market_structure_hash =
hash(
    sorted_seller_ids,
    fulfilment_mix,
    offer_count,
    lowest_effective_price,
    buy_box_owner
)
```

At delta_test_end:

Recompute.

If hash changes materially → quality_score reduces.

This makes validation cheap and automatic.

---

# Why This Is Critically Profitable

Because your profit engine depends on:

```
expected_share(P)
```

Expected share depends on:

```
learned_delta
```

If delta is wrong by even £0.10:

* And you sell 8 units/day
* That’s £0.80/day
* ~£292/year per SKU

Multiply across portfolio.

Bad learning is silent profit leakage.

---

# Protection Against False Aggressor Detection

Without outcome filtering:

Seller rotates → you lose Buy Box
System thinks: “Aggressor!”
You drop price aggressively

With invariants:

System sees no structural change → flags low-quality outcome → avoids escalation.

You avoid unnecessary duel.

---

# Structural Change in Master Plan

Under:

> Buy Box delta learning loop 

Add new mandatory section:

---

## Outcome Admissibility Layer (New)

Before updating delta bounds, the system must validate:

* competitor set stability
* no suppression
* no self stockout
* no major delivery shift
* no pricing health event

If invariants fail:

* mark test_result = contaminated
* do not update bounds (or apply weighted update)

Learning confidence must reflect admissible evidence only.

---

# Confidence Management

Delta record must include:

```
delta_confidence
valid_test_count
contaminated_test_count
last_valid_test_utc
```

Supervisor must refuse to use:

```
delta_confidence < minimum_threshold
```

In that case, system falls back to heuristic.

---

# Brutal Reality

A learning engine without outcome validation becomes:

> A noise amplifier.

Noise amplification leads to:

* Overreaction
* War escalation
* Margin destruction

Outcome validation makes it:

> A signal extractor.

Signal extraction produces:

* Stable deltas
* Accurate share prediction
* Smooth profit optimisation

---

# Final Summary

Old behaviour:

Win/Loss → Update delta.

New behaviour:

Win/Loss → Validate context → Weight update → Adjust confidence.

That single filter dramatically increases model reliability and long-term profitability.

---

If you want next, we can:

* Design the exact context_quality_score formula
* Or simulate a contaminated vs clean test to show how much margin this saves
* Or integrate this with seller aggression scoring so bad data never promotes a seller to Tier 2

This is the difference between a clever system and a durable one.
