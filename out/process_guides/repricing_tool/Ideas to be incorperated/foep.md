FOEP is useful, but only if you treat it as an **optional intelligence signal with explicit failure modes**. If you don’t, your ceiling logic will silently break on a non-trivial slice of your catalogue and your optimiser will either (a) overprice into no-sales or (b) underprice because it panics.

This needs to be encoded as a first-class rule set in your “eligibility ceiling” model.

---

## What FOEP actually gives you

FOEP is best thought of as:

> “A price boundary that often correlates with Featured Offer feasibility.”

It’s not guaranteed, and it’s not always returned.

So it should be used to:

* tighten the eligibility ceiling when present and trustworthy
* detect when your own delivery/metrics are limiting you
* reduce pointless probes above an infeasible boundary

Not to directly write a price. (You already have that right.)

---

## Why FOEP can be missing or unusable

You must explicitly handle:

1. **Endpoint returns no FOEP for an ASIN**
2. **Status: `ASIN_NOT_ELIGIBLE`**
3. **FOEP returned but low-confidence / inconsistent**
4. **FOEP returned but conflicts with other ceilings (CPT/compliance)**

Practical reasons (typical constraints):

* item condition (FOEP often expects New)
* “ship nationwide” type constraints
* you/offer not eligible to be featured offer
* listing not eligible

If you don’t encode these outcomes, you will treat “no FOEP” as “no ceiling” and accidentally widen the optimiser’s search space.

Wider space = more chances to pick a bad high price (no share) or a bad low price (margin bleed).

---

## How this helps profit

### 1) Prevents “fantasy pricing”

If FOEP is missing and you assume a high ceiling, the optimiser may pick a high price point that looks great on margin but produces no buy box share and kills units/day.

Explicit FOEP fallback prevents the optimiser from believing it can win at prices it can’t.

### 2) Prevents “panic undercutting”

If FOEP disappears and your system treats that as an error, it may drop to chase share. That destroys margin for no reason.

Explicit FOEP-unavailable handling keeps the system stable.

### 3) Keeps the ceiling model coverage complete

You will have SKUs where FOEP is never available. If your ceiling model depends on FOEP, those SKUs effectively have no robust ceiling logic and will behave inconsistently.

A deterministic fallback ladder gives full portfolio coverage, which improves average profit and reduces operational fire-fighting.

---

## The correct automatic logic

### Core concept: eligibility ceiling has a “source-of-truth ladder”

For each SKU each day (A-side refresh), compute:

* `eligibility_ceiling_gbp`
* `eligibility_source`
* `eligibility_confidence`
* `eligibility_reason_codes`

### Source ladder (strict order)

1. **FOEP (if available and valid)**
2. **CompetitivePriceThreshold (CPT)**
3. **Manual ceiling (BBP max sold / your maintained ceiling)**
4. **Historical highest winning price band (from your own win evidence)**
5. **Conservative fallback (e.g. best rival effective + small delta cap)**

Then clamp against compliance ceiling as normal.

This aligns with your “three ceilings” structure: compliance first, then eligibility, then demand. 

---

## FOEP availability decision rules

### FOEP usable when:

* FOEP returns a numeric price
* status indicates usable (not ineligible)
* price is non-zero and within sanity bounds vs current market (basic sanity check)

### FOEP not usable when:

* missing
* status = `ASIN_NOT_ELIGIBLE`
* status indicates offer not eligible / invalid input
* sanity check fails (e.g., FOEP absurdly low/high vs observed market, implying bad data)

When FOEP is not usable, you **must** set:

* `eligibility_source = fallback_<something>`
* `eligibility_reason_code = FOEP_UNAVAILABLE` or `FOEP_INELIGIBLE_ASIN` etc.
* `eligibility_confidence` lowered

This is important for auditability and for later analysis (“how many SKUs are running on FOEP vs CPT vs manual?”).

---

## How it integrates into the profit optimiser

In the H-cycle profit curve evaluation:

1. Pull `eligibility_ceiling_gbp` from Product DB (daily refreshed)
2. Build candidate price ladder only up to that ceiling
3. Run profit curve evaluation within `[hard_floor, min(eligibility_ceiling, demand_ceiling, compliance_ceiling)]`

This prevents the optimiser from choosing prices that are structurally infeasible to win.

---

## How it behaves across states

### Active competition

* Eligibility ceiling is binding
* If FOEP not available, CPT/manual/historical-wins provide a ceiling so you don’t drift into infeasible pricing.

### Low/no competition

* Demand ceiling tends to dominate, but eligibility ceiling still prevents “raise so high we stop being featured/visible”.
* FOEP missing does not break the ability to climb; it just changes which signal guards the climb.

---

## Required fields to add to your plan

Add these fields (Product DB / daily output):

* `foep_price_gbp`
* `foep_status`
* `foep_last_refresh_utc`
* `eligibility_ceiling_gbp`
* `eligibility_source` (FOEP / CPT / MANUAL / HIST_WIN / RIVAL_PLUS_DELTA)
* `eligibility_confidence`
* `eligibility_reason_codes`

And add an explicit health check:

* alert if `eligibility_source` is null
* alert if `foep_last_refresh_utc` stale > 48h (only if FOEP is expected for that SKU)
* distribution report: % SKUs by eligibility_source

This matches your “every new feature adds health checks” principle.

---

## Profit impact summary

* FOEP present → tighter, smarter eligibility ceiling → fewer wasted probes and fewer “price too high, no share” events → higher daily profit stability.
* FOEP missing but handled → no ceiling collapse, no panic behaviour → prevents margin bleed and avoids operational churn.
* Reason-coded fallbacks → you can later quantify where FOEP adds value and where you need alternative ceiling sources.

---

If you want this inserted as a clean MD section into your Master Working Plan, say “write as MD”, and I’ll format it as a drop-in section under “Eligibility ceiling model (daily refresh)” and “Health checks.”
