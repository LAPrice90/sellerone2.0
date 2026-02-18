Below is a **v8.1 Patch** designed to be appended to *Masterplan v8*  without rewriting any existing sections.

This patch addresses the remaining structural gaps:

1. Single-writer-per-SKU governance (PPP vs H-cycle conflict)
2. MVP share / units model for the profit optimiser
3. Variant identity fallback rules (shipping template reliability)
4. OAS hash tightening (separating structural vs promo contamination)

---

# v8.1 Patch — Runtime Safety + Optimiser Stabilisation Addendum

Status: Addendum to v8
Purpose: Production hardening before multi-SKU expansion

---

## 19) Single Writer Per SKU (Mandatory Arbitration Layer)

### 19.1 Why This Exists

If two systems write to the same SKU:

* You create artificial price wars.
* Delta learning becomes invalid (you learn from your own moves).
* Reaction-speed modelling becomes corrupted.
* OAS contamination increases.
* Profit optimiser fights ghosts.

This is not theoretical. It is guaranteed.

---

### 19.2 Pricing Writer Mode (Required Field)

Add per SKU:

```
pricing_writer_mode ∈ {PPP, CODEX_H, READ_ONLY}
pricing_writer_last_changed_utc
pricing_writer_reason_code
```

Rules:

* If `pricing_writer_mode = CODEX_H`

  * PPP must not reprice this SKU.
* If `pricing_writer_mode = PPP`

  * H-cycle must run in READ_ONLY (analysis only; no writes).
* If `READ_ONLY`

  * No automated writes allowed.

This must be enforced before Step 0 of the H-cycle decision flow.

---

### 19.3 Writer Conflict Invariant (Hard OAS Fail)

Add to OAS hard invariants:

If during probe window:

```
pricing_writer_mode changed
OR
external price write detected not from active writer
```

Then:

```
context_quality_score = 0
reason_code = WRITER_CONFLICT
```

No learning updates allowed.

---

### 19.4 Profit Impact

Prevents:

* False aggressor detection
* Artificial volatility
* Margin erosion due to self-competition

This alone protects portfolio stability.

---

## 20) MVP Share / Units Model (Profit Optimiser Stability Layer)

### 20.1 Why This Exists

Your optimiser chooses:

```
argmax(expected_profit_per_day)
```

But that depends on:

```
expected_units(P)
```

If share estimation is unstable, the optimiser will oscillate.

We need a safe, monotonic baseline model before complex modelling.

---

### 20.2 Baseline Units (Starter Rule)

Define:

```
baseline_units_per_day =
rank_based_estimate
× buy_box_win_rate_30d_adjustment
```

Must include confidence score:

```
baseline_units_confidence
```

If confidence low:

* Apply volatility penalty later.

---

### 20.3 Share Model (Monotonic Starter Function)

Define:

```
effective_gap = our_effective_price - best_rival_effective_price
```

Starter share curve:

```
if effective_gap <= -delta_confident:
    share ≈ high_share_cap (e.g., 0.7–0.9)
elif effective_gap between (-delta, +delta):
    share ≈ mid_share_band
else:
    share decreases smoothly toward 0
```

Requirements:

* Monotonic decrease as effective_gap increases
* Capped at upper bound
* Floor at minimum non-zero share (avoid division artifacts)
* Confidence-adjusted slope (flatter when delta_confidence low)

No oscillatory functions.
No sharp cliffs.

---

### 20.4 Volatility Penalty (Mandatory)

When:

* delta_confidence low
* OAS contamination ratio high
* variant_integrity_score low

Apply:

```
expected_profit_per_day *= volatility_discount_factor
```

This forces optimiser to avoid extreme ladder positions in unstable markets.

---

### 20.5 Shadow Mode Validation (Pre-Scale Requirement)

Before expanding to more SKUs:

* Run optimiser in shadow mode for N days.
* Compare:

  * predicted share vs observed share
  * predicted profit vs realised profit
* Require acceptable error band before activation.

---

### 20.6 Profit Impact

Prevents:

* Over-aggressive ladder jumps
* Oscillation
* Optimising into unrealistic volume assumptions

Stabilises contribution per SKU.

---

## 21) Variant Identity Reliability Fallback

### 21.1 The Problem

`shipping_template` may not be reliably observable.

If it fluctuates or is inferred incorrectly:

* One real variant splits into many (noisy learning)
* Or distinct variants collapse (floor contamination)

---

### 21.2 Shipping Template Confidence Field

Add per snapshot row:

```
shipping_template_confidence ∈ {HIGH, MEDIUM, LOW, UNKNOWN}
```

Add per variant:

```
variant_integrity_score ∈ [0,1]
```

---

### 21.3 Variant ID Generation Rule (Revised)

If `shipping_template_confidence` is LOW or UNKNOWN:

Exclude shipping_template from variant hash.

Fallback variant hash:

```
hash(
  marketplace_id,
  sku,
  seller_id_canonical,
  fulfilment_channel,
  condition
)
```

Mark:

```
variant_integrity_score -= penalty
reason_code = VARIANT_TEMPLATE_UNCERTAIN
```

---

### 21.4 Learning Gate

If `variant_integrity_score < integrity_threshold`:

* Allow optimisation.
* Block delta-bound updates.
* Degrade delta_confidence gradually.

---

### 21.5 Profit Impact

Prevents:

* Floor misestimation
* False aggressor promotion
* Oscillating seller classification

Stabilises learning → stabilises pricing.

---

## 22) OAS Hash Composition Tightening

### 22.1 Current Risk

Promo/coupon contamination is included in structure hash.

That makes too many windows hard-fail.

We separate structure vs posture properly.

---

### 22.2 Revised Hash Definition

#### Structure Hash (Hard Fail Only)

Include only:

* sorted offer_variant_id set
* fulfilment channel distribution
* condition distribution
* shipping template distribution
* offer_count

Exclude:

* promo/coupon flags
* price buckets
* Buy Box owner

---

#### Promo/Coupon Handling

Treat promo/coupon contamination as:

Hard invariant separately:

```
if promo_suspected_flag true:
    context_quality_score = 0
```

Do not mix it into structure hash.

---

### 22.3 Profit Impact

Prevents:

* Over-rejection of valid learning windows
* Stalled delta convergence
* Excessive fallback to heuristics

Learning continues where safe.

---

## 23) Hardening Checklist Before Expansion

Before expanding beyond pilot cohort, all must be true:

1. `pricing_writer_mode` enforced and conflict-free.
2. OAS contamination ratio < defined threshold.
3. Shadow-mode share error within acceptable band.
4. No SKU exceeds per-SKU API budget repeatedly.
5. Eligibility source distribution healthy (no null source).
6. Variant_integrity_score stable across key SKUs.
7. No inadmissible updates detected in audit logs.

---

# Final Assessment After v8.1 Patch

With these additions:

* Optimiser is profit-led and stable.
* Learning is quality-gated.
* Pressure is capital-governed.
* Scaling is event-led and rate-limited.
* Eligibility logic is deterministic and safe.
* Identity is structurally continuous.
* Writer conflicts are eliminated.

At that point, the plan is no longer just “intelligent”.

It becomes:

> Portfolio-grade and scale-safe.

---

If you’d like, next I can:

* Produce a **minimal implementation order (build sequence)** so you don’t try to build everything at once,
* Or simulate one SKU through the full pipeline (normal mode + pressure candidate + FOEP missing + notification event).
