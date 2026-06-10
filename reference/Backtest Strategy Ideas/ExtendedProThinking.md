You are on to something. The idea is sound. The mistake would be trying to jump straight from scraped chart history to a “perfect” self-optimizing repricer. The right build is simpler and stronger: one shared policy profile, a deterministic backtester that uses your existing H phase logic, and only then an optimizer fed by your own outcomes.

Amazon’s own seller material points the same way. Featured Offer outcomes are not just about price; Amazon ties them to competitive total price, shipping speed/cost, seller performance, stock levels, account standing, and condition. Amazon’s Pricing Health surfaces offers that are ineligible or near the Featured Offer price, Business Reports can show Featured Offer percentage over time, FBA and FBM can both be featured when other factors are equal, and Prime improves the chance of becoming Featured Offer. That means your scraped chart is a strong market signal, but it is not the whole truth on its own. ([Sell on Amazon][1])

Capital risk also has to sit inside the score, not outside it. Amazon’s public FBA material notes monthly storage fees and aged inventory charges on stock that sits in fulfillment centers beyond 181 days, so a listing that looks fine on snapshot ROI but regularly drifts into slow-turn or exit behavior is not actually a good buy. ([Sell on Amazon][2])

The clean design

Use one policy object for both sourcing and repricing. Not one target, but four thresholds:

```json
{
  "entry_target_roi": 20,
  "working_floor_roi": 10,
  "exit_floor_roi": 0,
  "emergency_floor_roi": -3,
  "fresh_stock_grace_days": 14,
  "low_velocity_units_14d": 2,
  "phase_days": [21, 35, 60, 90],
  "fast_track_under_floor_days": 14,
  "window_weights": { "90d": 0.5, "180d": 0.3, "365d": 0.2 }
}
```

That gives you the missing bridge:

* `entry_target_roi` is the buy rule.
* `working_floor_roi` is the normal operating floor.
* `exit_floor_roi` is the capital-recovery floor.
* `emergency_floor_roi` exists only for late live repricing phases.

That last part matters. Do not let phase 3 or phase 4 loss tolerance leak back into source approval. Otherwise the repricer becomes an excuse to buy weak listings.

How I would treat the market factors

* Buy Box history = upside ceiling. This tells you how often the market price was actually monetizable at your thresholds.
* Lowest FBA history = defendable floor. For an FBA-led model, this is the cleaner “real competition” line.
* The gap between Buy Box ROI and lowest-FBA ROI = compression risk. Big gap means the listing looks healthy until competition tightens.
* Amazon presence = override risk, not just another score input. If Amazon is in stock a lot, the rest of the chart matters less.
* FBM = conditional pressure only. Do not let a random low FBM offer wreck an FBA buy unless FBM actually wins the Buy Box or FBA is absent.
* Consecutive bad streaks matter more than averages. Your H logic already proves that. A 14-day under-floor streak is far more dangerous than scattered bad days.

For “why does someone have the Buy Box?”, keep the explanation probabilistic, not absolute. Amazon explicitly uses more than price, so your UI should show likely-cause tags with confidence, not fake certainty. High-confidence examples are Amazon in stock, lowest FBA also holding Buy Box, or obvious price compression. Lower-confidence cases are ties where seller metrics or shipping advantage may be deciding it. ([Sell on Amazon][1])

If you model FBM or SFP lanes, add a seller-fit multiplier from your own account health. Amazon says ODR, cancellation rate, and late shipment rate count against Featured Offer consideration, and its seller-fulfilled policy targets are ODR under 1%, late shipment under 4%, cancellation under 2.5%, and VTR at least 95%. ([Sell on Amazon][3])

How I would score the ROI bands

This is the part you were circling around, and the clean answer is:

* `20%+` = invest zone.
* `10–20%` = working zone.
* `0–10%` = exit zone.
* `<0%` = damage zone.

For sourcing, those should not be treated evenly.

`20%+` should be strongly positive.
`10–20%` should be mildly positive.
`0–10%` should be negative for sourcing, even though it is useful later for exits.
`<0%` should be strongly negative.

A good default weighting is:

```text
20%+   = +100
10–20% = +40
0–10%  = -40
<0%    = -100
```

That does three important things:

1. It keeps your current 20% snapshot pass meaningful.
2. It acknowledges that 10–20% is workable margin, but not a sourcing target.
3. It treats 0–10% as a warning that the ASIN may force you into sell-off behavior.

Do not score on average ROI alone. Averages will lie to you. Time-in-zone, longest streak, recovery speed, and phase-hit rate are what matter.

A practical score formula

For each day, calculate ROI twice:

* `roi_buybox`
* `roi_lowest_fba`

Then convert each daily ROI into a band weight.

A simple starting model:

```text
zone_score(series) = average(band_weight(day_roi))
```

Then combine the components:

```text
history_score =
    0.35 * zone_score(buybox_roi)
  + 0.25 * zone_score(lowest_fba_roi)
  + 0.15 * buybox_access_score
  + 0.10 * exit_recovery_score
  + 0.15 * (100 - amazon_risk_score)
  - streak_penalties
```

Starting defaults I would use:

* Heavy penalty if `max_consecutive_days_below_10 >= 14`
* Heavy penalty if `max_consecutive_days_below_0 >= 7`
* Hard fail or near-fail if Amazon holds Buy Box more than about 25–30% of sampled time
* Review, not instant fail, if there is often no Featured Offer; Amazon notes that can reflect stock, price, new-seller status, or low sales volume, so it is informative but not decisive by itself. ([Sell on Amazon][1])

A clean pass system would be:

* `current_roi >= entry_target_roi` is still the hard current gate.
* `history_score >= 70` = pass.
* `55–69` = review.
* `<55` = fail.

That gives you flexibility without turning the model soft.

The real bridge to your H strategy

This is the part that makes the idea worth building.

Your source checker should not only say “good history” or “bad history.” It should answer:

“If I had bought this ASIN on any historical start date, how often would my H engine have stayed in protection, how often would it have hit margin compression, and how often would it have been forced into controlled exit or liquidation?”

That means the backtester should output at least:

* `phase_2_hit_rate`
* `phase_3_hit_rate`
* `phase_4_hit_rate`
* `median_days_to_sale`
* `median_realized_roi`
* `max_adverse_margin_excursion`
* `capital_days_locked`
* `exit_without_loss_rate`

That is your TradingView equivalent. Not a chart narrator. A policy simulator.

How to backtest it properly

Use rolling historical start dates.

For each date `T` in history:

1. Use only information available up to `T` to decide whether the ASIN passes.
2. If it passes, simulate buying one unit at your cost basis on `T`.
3. Run the same H state machine forward through the price history from `T+1`.
4. Record sale date, realized ROI, phase reached, and whether emergency floor was needed.
5. Repeat across all start dates and aggregate.

That avoids look-ahead bias in the decision logic.

One hard truth: price history alone is not enough to optimize “income.” It is enough to optimize margin path and capital risk. To optimize income, you also need demand. Otherwise you are guessing turnover. The easiest way to fix that is to join the chart data with your own ordered sales, units sold, average selling price, page views, and Featured Offer percentage over time. Amazon’s Business Reports now expose those kinds of metrics, which makes them useful calibration data for the next stage. ([Sell on Amazon][4])

Can the sourcing model and repricer feed each other?

Yes, and they should.

The right feedback loop is:

* The source checker predicts whether an ASIN is worth entering under profile X.
* The repricer executes profile X live.
* Your live outcomes tell you where the source checker was too optimistic or too strict.
* The backtester recalibrates the weights, thresholds, and phase penalties.

That is the right direction.

Could you eventually optimize repricing settings from historical data?

Yes, but not from scrape-only data as a first step.

The research side supports the idea. Contextual bandits have been used for real-world e-commerce markdown pricing to maximize margin and clear inventory. Off-policy evaluation is attractive because live experimentation in pricing is costly. But the same research also warns that standard inverse-propensity and doubly-robust methods can perform badly when the historical pricing policy is deterministic or has little exploration, which is common in pricing. Separate work on stateful offline policy evaluation is directly relevant when inventory state and sequential decisions matter. In plain English: the later optimizer is real, but it needs your own logged actions and outcomes, not just scraped competitor charts. ([ACM Digital Library][5])

My blunt recommendation

You are not overcomplicating the destination. You would be overcomplicating phase one if you tried to build the optimizer first.

Build this in order:

1. One shared policy profile.
2. One deterministic rolling backtester using your H logic.
3. One source score based on band occupancy, streaks, Amazon risk, and phase-hit rates.
4. Only after that, add demand calibration and parameter optimization.

The single most important design choice is this: keep `20%` as the entry target, keep `10%` as the working floor, keep `0%` as the exit floor, and treat anything below that as damage. That preserves discipline while still letting history tell you whether a listing would have forced you into sell-off behavior.

Next step should be defining the exact profile schema and the backtest outputs before touching any optimization layer.

[1]: https://sell.amazon.com/blog/buy-box-featured-offer "Maximize Your Sales Potential with the Amazon Featured Offer (formerly Buy Box) - Sell on Amazon"
[2]: https://sell.amazon.com/blog/ask/amazon-fba-beginners-guide-2026?utm_source=chatgpt.com "Amazon FBA beginner's guide 2026"
[3]: https://sell.amazon.com/blog/amazon-pricing-strategies "Amazon pricing strategies: How to price products to drive sales - Sell on Amazon"
[4]: https://sell.amazon.com/blog/amazon-business-reports "Get actionable B2B insights with Amazon business reports - Sell on Amazon"
[5]: https://dl.acm.org/doi/10.1145/3632410.3632448?utm_source=chatgpt.com "Contextual Bandits for Online Markdown Pricing for E- ..."
