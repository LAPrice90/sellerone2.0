You are on to something.

The mistake would be building a static “chart score.” The right build is a **single pricing policy engine** that powers three things at once: the sourcing check, the live repricer, and the historical backtest. That keeps the logic consistent, so the history tells the same story your live system will actually follow.

Amazon’s current pricing stack points in exactly that direction. Featured Offer visibility is not just “lowest price wins”: Amazon says it considers price, delivery speed, seller performance, and availability, and also notes that faster delivery dates are more likely to be shown as the Featured Offer. Amazon’s own repricing stack is built around Product Pricing plus `ANY_OFFER_CHANGED` and `PRICING_HEALTH`; `ANY_OFFER_CHANGED` tracks top-offer and Buy Box changes, `PRICING_HEALTH` fires when an offer becomes Buy Box-ineligible because of uncompetitive pricing, and FOEP gives the price at or below which a seller can expect to become the Featured Offer, though not with a guarantee because competitors and fulfillment context can change. ([Seller Central][1])

One important limitation: Amazon also says competitive price thresholds can come from reputable retailers **outside** Amazon, not just other Amazon sellers. So scraped Amazon chart history is powerful, but it is not the full truth about eligibility. Your model should include a small uncertainty haircut rather than assuming Amazon-only price history captures every Buy Box risk. Also, Amazon’s `ANY_OFFER_CHANGED` only works for ASINs where you already have an active offer, which is exactly why scraped chart history remains useful for pre-buy sourcing decisions. ([developer-docs.amazon.com][2])

Research also supports the path you are thinking about. Dynamic pricing with external information and inventory constraints is a standard optimization problem, offline historical data materially changes online pricing performance, and recent work has already applied contextual-bandit methods to e-commerce markdown pricing. So the sensible route is: build a historical simulator first, then add parameter optimization, and only later consider more advanced learning methods. ([PubsOnline][3])

## What I would build

Use one shared policy object in the UI.

```json
{
  "profile": "FBA/FMA_like",
  "grace_days": 14,
  "phase_days": {
    "bias": 21,
    "compression": 35,
    "exit": 60,
    "liquidation": 90
  },
  "target_roi": {
    "protect": 0.20,
    "bias": 0.20,
    "compression": 0.10,
    "exit": 0.00,
    "liquidation": -0.03
  },
  "fast_track": {
    "below_hard_floor_days": 14
  },
  "min_valid_window_hours": 12,
  "recency_weights": {
    "30d": 0.50,
    "90d": 0.30,
    "180d": 0.20
  },
  "amazon_penalty_mode": "high"
}
```

Every repricing setting in the UI should write into that same object. The sourcing checker reads it. The repricer reads it. The backtester reads it.

That is the key simplification.

## How to treat each factor

Assumption: your selling profile behaves closer to FBA than to ordinary FBM. If your “FMA” behaves differently, only the fulfillment multipliers change.

1. **Buy Box history = primary signal**
   This is the closest thing to “real sale opportunity.” Do not score single touches. Score **dwell time** in band and **who held it**.

2. **Lowest FBA = strong secondary signal**
   For an FBA/FMA-like seller, lowest FBA is the main competitive floor.

3. **Lowest FBM = context, not truth**
   Because delivery speed matters, a low FBM price should not force you to assume an FBA/FMA offer must match it exactly. Treat FBM as weaker unless FBM is regularly holding the Buy Box. That is consistent with Amazon explicitly weighting delivery speed in Featured Offer visibility. ([Seller Central][1])

4. **Amazon presence = separate penalty, not just another line**
   Amazon in stock changes the whole market. It should be a risk overlay, not a normal price input.

5. **Longest streaks matter more than average time**
   A listing spending 20% of time in 0–10% as short dips is very different from sitting there for 25 consecutive days.

6. **Recency must beat old history**
   Use at least 30/90/180-day weighting. Old chart behaviour should not dominate recent structure.

My starting weighting for an FBA/FMA-like sourcing model would be:

```text
Buy Box opportunity        50%
Lowest FBA support         25%
Lowest FBM context         10%
Amazon suppression         penalty overlay
Streak / recovery risk     penalty overlay
Recency weighting          applied to all of the above
```

And my starting holder multipliers would be:

```text
FBA holds Buy Box      1.00
FBM holds Buy Box      0.75
Amazon holds Buy Box   0.30
No clear Buy Box       0.50
```

## How I would score the ROI bands

Your key insight is correct: **0–10% is not a universally bad band. It is a time-dependent band.**
Early on, it is a trap. Later on, it is a valid exit.
So do **not** give one global score to 0–10%.

Score the same ROI ranges differently by phase:

```text
Days 0–20   : 20%+ = 100 | 10–20% = 40 | 0–10% = 0  | <0% = -100
Days 21–34  : 20%+ = 100 | 10–20% = 60 | 0–10% = 5  | <0% = -100
Days 35–59  : 20%+ = 100 | 10–20% = 80 | 0–10% = 15 | <0% = -90
Days 60–89  : 20%+ = 100 | 10–20% = 80 | 0–10% = 45 | <0% = -60
```

Two important rules:

* For **sourcing**, treat `90+ days` only as a **risk output**, not as positive justification to buy.
* For **repricing**, `90+ days` is where liquidation logic can exist, but products that frequently need it should still fail sourcing.

That means:

* `20%+` = target trade zone
* `10–20%` = acceptable working zone
* `0–10%` = capital recovery zone, only useful late
* `<0%` = forced-loss zone

## Do not make the final decision from band points alone

Use the band points internally, but show the final decision as **outcomes** from a walk-forward simulation.

For each historical possible buy date, simulate your H-style policy forward and record:

* `P(ROI >= 20% by Day 35)`
* `P(ROI >= 10% by Day 60)`
* `P(ROI >= 0% by Day 90)`
* `FastTrackRate` = how often the 14-day-below-floor rule would have triggered Phase 3 early
* `LiquidationRate`
* `MedianDaysToFirstValidSellWindow`

That gives you a much cleaner score than “average chart looked okay.”

My starting portfolio decision score would be:

```text
DecisionScore =
0.35 * Hit20By35
+ 0.25 * Hit10By60
+ 0.20 * BreakevenBy90
+ 0.10 * (100 - FastTrackRate)
+ 0.10 * (100 - LiquidationRate)
```

Starting hard fails:

```text
FastTrackRate > 15%
BreakevenBy90 < 85%
MedianDaysTo10% > 60
```

Starting pass bands:

```text
Pass   : DecisionScore >= 70
Warn   : 55 to 69
Fail   : < 55
```

Those are starting values, not laws. The backtester should tune them later.

## Could the sourcing checker and repricer feed each other?

Yes. That is the whole point.

The same policy object should drive both:

* **Before buy**: “Would this ASIN historically have worked under my actual repricing behaviour?”
* **After buy**: “Run that exact policy live.”
* **After enough data**: “Which settings historically gave the best profit/capital-risk tradeoff?”

That is your TradingView-style loop.

## How to optimize repricing settings without fooling yourself

Do not optimize for “highest income” only. That will overfit to aggressive settings and trap cash.

Optimize on a frontier:

```text
Gross profit
Average realized ROI
Average capital days
% units reaching Phase 3
% units reaching Phase 4
Worst-decile ROI
Forced liquidation rate
```

A good objective is something like:

```text
Objective =
GrossProfit
- λ1 * CapitalDays
- λ2 * ForcedExitUnits
- λ3 * NegativeROIUnits
```

Then sweep parameters like:

```text
grace_days        [10, 14, 21]
compression_day   [28, 35, 42]
exit_day          [45, 60, 75]
liquidation_day   [75, 90, 105]
target_roi        [18%, 20%, 22%]
compression_floor [8%, 10%, 12%]
exit_floor        [-2%, 0%, 2%]
fast_track_days   [7, 14, 21]
amazon_penalty    [low, medium, high]
```

Use **walk-forward validation**, not one giant in-sample run. Optimize on one historical block, validate on the next block. That is the simplest way to stop yourself tuning to noise.

## The honest limitation

Scraped price history is enough to estimate **market opportunity** and **capital risk**.

It is **not enough** to estimate true realized income on its own, because it does not tell you exactly how many units would have sold at each price. For a true optimizer, you eventually need to join in your own order data, inventory age, and sell-through. Amazon’s live seller tooling also includes retail analytics signals such as detail page traffic, item sales events, and sales/traffic reports, which can improve the model once you actually list the item. ([developer-docs.amazon.com][4])

## Bottom line

You are not overcomplicating the business problem. You are only at risk of overcomplicating the build.

The clean version is:

1. One shared pricing policy.
2. Phase-aware ROI scoring.
3. Walk-forward simulation on scraped history.
4. Final decision from outcome probabilities, not raw band averages.
5. Optimizer on profit **and** capital lock, not profit alone.

That will give you a sourcing checker that matches your repricer instead of fighting it.

The next useful deliverable is a field-by-field scoring spec and the exact walk-forward algorithm against your current H engine.

[1]: https://sellercentral.amazon.co.uk/help/hub/reference/external/GHEZQUQYZSPGXHG3?locale=en-GB%2B%3Cseller%EF%BF%BDs%2Bpolicy%3E&utm_source=chatgpt.com "How products are given visibility in the Amazon store"
[2]: https://developer-docs.amazon.com/sp-api/docs/pricing-faq "https://developer-docs.amazon.com/sp-api/docs/pricing-faq"
[3]: https://pubsonline.informs.org/doi/10.1287/mnsc.2023.4963 "Dynamic Pricing with External Information and Inventory Constraint | Management Science"
[4]: https://developer-docs.amazon.com/sp-api/docs/sp-api-seller-use-cases "https://developer-docs.amazon.com/sp-api/docs/sp-api-seller-use-cases"
