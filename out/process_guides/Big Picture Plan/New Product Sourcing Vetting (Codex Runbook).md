# New Product Sourcing Vetting (Codex Runbook)

## Purpose of this file
- This runbook is for pre-buy product decisions.
- It is separate from live listing competition execution.
- Goal: avoid buying into listings that look good on sales but fail on competitive behavior and margin durability.

## Scope boundary
- In scope:
- decide if a new SKU is worth buying
- observe listing behavior before first order
- assign clear go/no-go decision with evidence
- use BBP table and BBP dataset as primary new-product inputs
- Out of scope:
- live repricing execution after stock is purchased
- daily seller-vs-seller tactical play

## Core principle
- A product must pass both:
- sales potential test
- behavior risk test
- If either fails, do not buy.

## End-to-end flow

### Stage 1 - Intake
- Collect SKU/ASIN candidate and baseline economics.
- Record:
- landed unit cost
- expected fees
- target margin
- stock commitment options (small, medium, large)

### Stage 2 - Sales Fit Gate
- Apply existing product criteria list.
- Example checks:
- demand level
- seasonal risk
- margin at realistic market price
- If failed:
- decision = `NO_GO_SALES`
- stop process.

### Stage 3 - Observation Gate (no stock purchase yet)
- Run observation window before first order.
- Default window:
- 14 days minimum
- 30 days preferred for medium/high spend buys
- Capture:
- who holds Buy Box and how often
- how fast top competitors react to undercuts
- delivery advantage patterns
- repeated price-war patterns
- seller churn and re-entry behavior

### Stage 4 - Risk Scoring
- Build simple risk scores:
- `price_war_risk_score`
- `delivery_disadvantage_risk_score`
- `aggressor_density_score`
- `floor_instability_score`
- `expected_defensive_profit_per_month_gbp`
- Use defensive scenario, not ideal scenario.

### Stage 5 - Go/No-Go decision
- Decision outputs:
- `GO`
- `GO_SMALL_TEST_BUY`
- `NO_GO_BEHAVIOR_RISK`
- `NO_GO_MARGIN_RISK`
- Required decision notes:
- top 3 reasons
- confidence level
- what would change this decision

## Minimum data requirements

### BBP listing-level (primary)
- asof_date
- sku
- asin
- buy_box_owner
- buy_box_price_gbp
- offer_count_total
- stock_visible_or_estimated
- review_count
- sales_rank_primary
- sales_rank_category
- sales_rank_trend_7d
- sales_rank_trend_30d
- product_rating_value
- delivery_promise_days

### BBP offer-level (primary)
- seller_id
- fulfilment_channel
- listing_price_gbp
- shipping_price_gbp
- landed_price_gbp
- min_delivery_days
- max_delivery_days
- effective_price_gbp
- roi_estimate_pct
- profit_estimate_gbp

### Seller-level (lightweight)
- seller_id
- seller_feedback_score_pct
- seller_feedback_count
- simple_price_behavior_note

### Optional enrichment (only if already available)
- seasonality_index_month
- historical_reentry_notes
- promo_or_coupon_flag

## Decision rules (starter defaults)
- Sales fit must pass.
- Observation minimum must be met.
- Reject if:
- expected defensive monthly profit < 30 GBP
- and high war risk is present
- Prefer `GO_SMALL_TEST_BUY` when confidence is medium and uncertainty is still high.
- Rank context rule:
- if rank trend is deteriorating and volatility is high, downgrade one decision level (`GO` -> `GO_SMALL_TEST_BUY`, `GO_SMALL_TEST_BUY` -> `NO_GO_MARGIN_RISK`) unless margin buffer is exceptional.

## Warning signs that force caution
- Buy Box changes hands very frequently with tight price spacing.
- One or more aggressive sellers repeatedly chase to a low floor.
- We require a deep discount to win but margin buffer is weak.
- Delivery gap repeatedly blocks conversion even when price is close.
- Seller re-entry patterns restart wars after short calm periods.

## Integration with live competition plan
- If decision is `GO` or `GO_SMALL_TEST_BUY`:
- create handoff record to competition intelligence runbook
- include opening strategy assumptions and guardrails
- If decision is `NO_GO`:
- retain case for learning
- review only if major market changes occur

## Exit and re-entry expectation
- If we leave a listing, keep rank and market behavior snapshots so re-entry is predictable.
- Required re-entry fields:
- last_seen_sales_rank
- rank_delta_since_exit
- competitor_density_delta_since_exit
- expected_reentry_price_band_gbp
- expected_reentry_war_risk
- Re-entry rank interpretation:
- if rank is materially worse on return than at exit (example: 5000 to 12000 in same category), assume lower demand and lower baseline units until new live evidence confirms recovery.
- Apply context checks before finalizing:
- category unchanged
- no major market price shift
- no temporary stockout distortion
- month-to-month seasonality effect

## Evidence package required per decision
- Snapshot period dates
- candidate count and filtered count
- key seller behavior summary
- defensive profit scenario table
- final decision and reason codes

## Things to avoid
- Buying based on demand alone.
- Using only lowest offer price without delivery/value adjustment.
- Assuming today's calm market means low future aggression.
- Skipping observation on high-spend buys.

## Open questions
- Final threshold for defensive monthly profit by category.
- Best default observation window by risk tier.
- Trigger for re-review of previously rejected candidates.
- Confidence scoring formula for go/no-go.
- BBP-to-internal field mapping standard for each marketplace.

## Change management
- Add new ideas here first.
- Keep this file as the master for new product vetting.
- Do not merge this with live execution logic.
