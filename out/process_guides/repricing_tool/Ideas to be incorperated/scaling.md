## What this is fixing

Your current scaling plan is directionally correct: **listen-only Notifications first**, then event-triggered refresh, then expand.

The missing piece is treating notifications as a **core dependency** of the pricing runtime, not an “engineering enhancement later”.

If you scale without it, you will eventually hit:

* API throttling → stale snapshots → wrong pricing decisions
* Over-polling → higher cadence costs → more price churn
* Missed “pricing health” events → suppression risk
* Portfolio instability → profit down, operational stress up

---

## Why BOTH `ANY_OFFER_CHANGED` and `PRICING_HEALTH` are required

They are not substitutes. They cover different failure domains:

### `ANY_OFFER_CHANGED` (Market movement detector)

Use it to detect:

* competitor price change
* shipping/delivery promise change
* offer appearance/disappearance
* coupon/promo changes (depending on what your downstream snapshot reveals)

**How it helps profit**

* You stop checking quiet SKUs every 15 minutes “just in case”.
* You only refresh SKUs that actually moved.
* Less churn means fewer unnecessary undercuts and fewer panic drops.

### `PRICING_HEALTH` (Risk detector)

Use it to detect:

* listing/offer entering a pricing-risk state
* ineligibility conditions that can remove Featured Offer eligibility
* situations where “being lowest” doesn’t matter because you’re disqualified

**How it helps profit**

* Prevents silent suppression/eligibility loss (profit goes to zero fast when visibility dies).
* Stops the system from running futile duels when the constraint is policy/health, not competition.

**Practical conclusion**

* `ANY_OFFER_CHANGED` triggers *tactical refresh*.
* `PRICING_HEALTH` triggers *risk override / clamp / freeze*.

This maps cleanly to your Head/Supervisor/Executioner control hierarchy and “trigger overrides” concept.

---

## The event-driven runtime architecture

### Core rule

**The scheduler must be event-led, polling is fallback only.**

You already wrote this as a pre-expansion gate. The improvement is: make it the default architecture now.

### Data flow

1. **Notification intake (always-on, cheap)**

* Store events to an append-only log + a lightweight “event inbox” keyed by SKU/ASIN.
* Deduplicate events by `(sku, event_type, short_time_window)` to avoid stampedes.

2. **Event → Targeted refresh decision (Supervisor responsibility)**

* For each SKU with events, decide refresh urgency:

  * immediate (now)
  * soon (within 15–30m)
  * defer (batch later)

3. **Targeted refresh (Executioner)**

* Pull only what’s needed to make a decision:

  * updated offer snapshot
  * updated buy box state
  * updated effective prices
* Run profit-optimizer decision for that SKU only.

4. **Fallback heartbeat polling**

* Low-frequency “are we blind?” check:

  * once every 4–8 hours per SKU depending on state
* Purpose: cover missed notifications / integration outages.

This is exactly aligned with your “cadence by state” model (parked/monitor/duel/wait_out). 

---

## Rate-limit observability and per-SKU budgets

Scaling fails when “refresh everything” hits rate limits and your system silently becomes stale.

### What you need to track (every API call)

* remaining quota / burst capacity (from response headers)
* actual call cost (some endpoints are heavier)
* timestamp
* SKU that consumed the budget
* endpoint name

### The budget model (simple and effective)

Define two layers of budgets:

#### Global budgets

* “Hard stop” when remaining capacity drops below safety threshold.
* Prioritize PRICING_HEALTH-driven actions over ANY_OFFER_CHANGED refreshes.

#### Per-SKU budgets

Each SKU gets a daily/rolling window budget based on lane + volatility:

* Passive SKU: tiny budget
* Managed SKU: moderate budget
* Micro-managed / duel SKU: higher budget, but capped

This prevents one chaotic SKU from eating the entire system’s capacity and blinding the rest of the portfolio.

### Why this is profitable

* You avoid “stale market truth” which causes wrong moves.
* You keep high-value SKUs responsive while low-value SKUs don’t waste resources.
* You reduce churn and protect margin.

---

## Automatic logic you can implement immediately

### Trigger mapping

* If `PRICING_HEALTH` event:

  * Set SKU state override: `defensive_hold` or `parked`
  * Force clamp to compliance ceiling
  * Require Supervisor review before any aggressive action
* If `ANY_OFFER_CHANGED` event:

  * If SKU in duel/wait_out → refresh now
  * If SKU in monitor → refresh soon (batch)
  * If SKU parked → ignore unless seller-of-interest re-entry detected

### Event storm control

* Add a per-SKU cooldown on refresh:

  * “At most one refresh per X minutes unless PRICING_HEALTH”
* Batch refreshes across SKUs to smooth API usage.

### Observability outputs (must exist)

* `notifications_last_seen_utc` per SKU
* `event_backlog_age_seconds`
* `calls_used_today_by_sku`
* `calls_used_today_total`
* `rate_limit_near_exhaustion_flag`

This should be part of your health checks, same as you require for every new feature.

---

## What changes in your rollout gate

Your existing gate says “build notifications before full rollout”. 

The upgrade is:

**No SKU expansion until both are true:**

1. Notifications reliably received for pilot SKUs (multi-day)
2. Per-SKU budgets demonstrably prevent one SKU from starving others
3. Pull volume is materially reduced vs baseline polling
4. No missed PRICING_HEALTH alerts in the validation window

This converts notifications from “nice-to-have” into “portfolio safety system”.

---

## Bottom line

* `ANY_OFFER_CHANGED` = tells you where to look.
* `PRICING_HEALTH` = tells you when not to play the game.
* Rate-limit observability + per-SKU budgets = keeps you from going blind as you scale.