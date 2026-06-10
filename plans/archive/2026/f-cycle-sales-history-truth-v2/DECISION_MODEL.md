# Decision Model

## Core question
- The system is not trying to answer:
  - how many sales did BBP estimate in total
- The system is trying to answer:
  - if we buy this now, how many sales are likely available to us at our economics, and what monthly profit does that imply

## Rule 1 - Trusted sales history
- Use completed months only as trusted demand history.
- Current month is observability-only.
- Future predicted months are ignored.
- If no completed month exists, the row is not allowed to pretend it has trusted demand.

## Rule 2 - Raw demand versus qualified demand
- Keep two separate numbers:
  - `raw_observed_monthly_units`
    - what the market appears to have sold
  - `price_qualified_monthly_units`
    - what we could reasonably participate in at our floor and share assumptions
- Only `price_qualified_monthly_units` should drive the buy decision.
- Break-even-only sales are useful context, but they do not count as healthy demand for buying.

## Rule 3 - History maturity
- `no_history`
  - 0 completed months
  - normally `fail` or `manual_review`
- `recent_only`
  - 1 to 2 completed months
  - no seasonality claim allowed
  - confidence low
- `developing`
  - 3 to 5 completed months
  - recent trend can be read
  - seasonality still not trusted
- `stable`
  - 6 to 8 completed months
  - stability can be judged
  - only weak or possible seasonality claim allowed
- `full_year`
  - 9 to 12 completed months
  - full seasonality read allowed

## Rule 4 - How much history should be recognized
- Buy-now forecast should use three layers:
  - last completed month
  - trailing 3 completed months
  - full 12-month context when available
- Default decision weighting:
  - 50 percent last completed month
  - 30 percent trailing 3 completed month average
  - 20 percent full-history context
- Old history can raise risk, but it must not rescue weak current economics.

## Rule 5 - Seasonality
- We need 9 to 12 completed months before calling seasonality with confidence.
- A product is `seasonal_confirmed` only when both are true:
  - the strongest 2 to 4 adjacent months account for at least 50 percent of annual qualified units
  - off-season months are materially weaker than the peak window
- First working threshold for "materially weaker":
  - off-season average qualified units should be at or below 50 percent of peak-window average qualified units
- A product is `possible_seasonal` when the shape looks seasonal but history maturity is only `stable`, not `full_year`.
- A product is `spiky_not_proven_seasonal` when one or two months are strong but the full pattern is not repeatable enough to trust.

## Rule 6 - Stability
- Stability is separate from seasonality.
- Use plain business states:
  - `stable`
  - `drifting_down`
  - `drifting_up`
  - `spiky`
  - `too_new`
- A listing is not `stable` if one or two months dominate without a seasonal pattern.
- First working thresholds:
  - `too_new`
    - fewer than 3 completed months
  - `spiky`
    - top completed month is at least 2.5x the median completed-month qualified units
    - and seasonality is not confirmed
  - `drifting_down`
    - trailing-3 completed-month qualified average is below 80 percent of the listing baseline
  - `drifting_up`
    - trailing-3 completed-month qualified average is above 120 percent of the listing baseline
  - `stable`
    - enough maturity exists
    - and none of the above states wins

## Rule 7 - Recent performance
- Recent performance means:
  - how the last completed month and the trailing 3 completed months compare to the listing's own baseline
- Recent state labels:
  - `underperforming`
  - `stable`
  - `overperforming`
  - `insufficient_history`
- First working thresholds:
  - baseline:
    - trailing completed-month qualified average across the recognized history window, excluding predicted months
  - `underperforming`
    - last completed month below 80 percent of baseline
    - or trailing-3 below 85 percent of baseline
  - `overperforming`
    - last completed month above 120 percent of baseline
    - or trailing-3 above 115 percent of baseline
  - `stable`
    - neither underperforming nor overperforming threshold is hit
  - `insufficient_history`
    - fewer than 3 completed months
- Recent under/over calls must always include a reason tag where possible:
  - `seasonal_window`
  - `amazon_below_floor`
  - `market_below_floor`
  - `recent_price_compression`
  - `high_volatility`
  - `insufficient_history`

## Rule 8 - Price qualification
- We cannot count all historical sales equally.
- Sales from periods where the sellable market sat below our floor are not truly available to us.
- First working rule:
  - count only the portion of monthly demand that happened while the market was above our working floor
  - discount or exclude demand when Amazon or the market price sat below our floor
  - apply our share assumption to the remaining sellable demand
- This creates:
  - `price_qualified_monthly_units`
  - `price_qualified_monthly_profit_gbp`

## Rule 9 - Commercial floor
- Working commercial floor for this phase:
  - expected monthly profit must normally be above `GBP 20`
- If expected monthly profit is below `GBP 20`, the row should normally fail even if it is above break-even.
- Exceptions must be explicit and never hidden inside confidence language.

## Rule 10 - Confidence
- `high`
  - full-year history
  - clean completed-month demand basis
  - validation sample close to operator check
  - no major join or attribution problems
- `medium`
  - at least developing/stable history
  - minor gaps but still enough to trust directionally
- `low`
  - too little history
  - unresolved joins
  - weak attribution
  - validation not proven

## Rule 11 - Decision output
- Every row must end in one of:
  - `pass`
  - `fail`
  - `manual_review`
- The output must also say:
  - expected units now
  - expected profit now
  - maturity state
  - seasonality state
  - recent performance state
  - confidence
  - reason codes

## Rule 12 - Post-purchase learning
- When we decide to buy, save the assumption at that moment:
  - cost
  - floor
  - expected units
  - expected profit
  - seasonality read
  - recent-performance read
  - confidence
- Then review the next 90 days and classify:
  - right call
  - demand too high
  - demand too low
  - price assumption wrong
  - Amazon suppressed it
  - seasonality misread
  - operational issue blocked outcome

## Plain-English summary
- We do not want the system to tell us what sold.
- We want it to tell us what was sellable for us, how trustworthy that history is, what we should expect now, and how we will learn when it is wrong.
- The current dataset is now strong enough to implement these rules.
- Broad scraping is no longer the blocker.
- Remaining scrape failures belong in a targeted cleanup lane, not in the main decision-model lane.
