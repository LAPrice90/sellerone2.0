# Research Report

## Question
- How much useful feedback do H repricer and F new product finder already collect, what is missing, and what should the next task build?

## Short answer
- We already collect enough raw data to build a real learning loop.
- H is not data-poor. It is feedback-poor.
- F is not framework-poor. It is reality-link-poor.
- The next task should build a joined learning layer first, then operator reports, then shadow calibration into F, and only then live strategy experimentation.

## What H already captures

### Runtime strategy facts
- `out/h_strategy_outcome_log.csv`
  - `9755` rows
  - includes scenario, chosen tactic, before/after buy box state, seller count, ladder prices, our price before, target price, written price, response window, writer outcome, terminal outcome, reason codes
- `out/h_strategy_outcome_daily.csv`
  - `33` rows
  - includes decision/applied/no-write/resolved/pending/success/failed/expired/aborted counts plus seller-count and price-gap averages
- `scripts/phase1/phase1_main_loop.py` already classifies tactic states into learning-friendly scenario buckets such as `share_hold`, `suppression_reactivation`, `controlled_exit`, `single_rival_reset`, and `multi_seller_ladder_cap`

### Market and seller facts
- `out/listing_offer_snapshot_latest.csv`
  - `65` rows
  - listing-level price, buy box, offer-count, seller-detail, and BSR context
- `out/listing_offer_seller_snapshot_latest.csv`
  - `529` rows
  - seller-level landed price, fulfilment channel, prime, delivery window, and seller-detail state
- `out/listing_offer_history.csv`
  - `2462` rows
- `out/listing_offer_seller_observation_history.csv`
  - `9602` rows
- `out/h_seller_profiles.csv`
  - `78` rows
- `out/h_seller_of_interest.csv`
  - `34` rows
- `out/h_seller_delta_learning.csv`
  - exists but only `2` rows right now, so the learning layer is barely seeded

### Market snapshot facts already prepared for operator use
- `out/hos_daily_market_snapshot_latest.csv`
  - `57` rows
  - columns already include:
    - buy box price
    - lowest FBA and FBM
    - offer counts
    - Amazon-present flag
    - seller entry and exit counts
    - delivery parity
    - break-even and price anchors
- `out/reports/hos_daily/...`
  - HTML and PDF market reports already exist

### Sales and economics facts that can be joined back to H
- `out/sku_performance_summary.csv`
  - `159` rows
  - units, velocity, ROI, break-even, profit-per-unit, reorder hints
- `out/sku_sales_velocity.csv`
  - `477` rows

## What H already tells us today
- Latest scenario distribution from `out/h_strategy_outcome_log.csv`:
  - `share_hold`: `5265` rows
  - `multi_seller_ladder_cap`: `2967` rows
  - `raise_find_loss`: `1195` rows
  - `suppression_reactivation`: `310` rows
  - `controlled_exit`: `25` rows
- Latest listing snapshot signs:
  - `65/65` rows have us present
  - `62/65` rows have buy box present
  - seller detail is mostly healthy:
    - listing snapshot: `62 DETAIL_OK`, `3 DETAIL_EMPTY_RESPONSE`
    - seller snapshot: `529 DETAIL_OK`
- Current H scoped warnings still matter:
  - `multi_seller_ladder_cap` expired share is still too high
  - `single_rival_reset` sample is still too small

## What H does not yet do
- It does not persist a clean link from:
  - market state
  - to H action
  - to later sales result
  - to tactic success by factor bucket
- It does not explain:
  - how often we are being undercut
  - how long rivals hold low prices before moving
  - whether matching improved or harmed our share
  - whether a reset-up move actually changed later market behavior
  - which competitor-count bands deserve different logic
- It does not create a monthly alignment view against actual sales.
- It does not expose strategy cohorts or controlled experiments.
- It does not give operator-grade "what changed because of this rule" reporting.

## What F already captures

### F already has calibration and validation structure
- `out/analysis_reports/f_backtest_calibration_set_latest.csv`
  - `18` sampled review rows
- `out/analysis_reports/f_backtest_calibration_set_latest.md`
  - grouped learning cases and plain-English review prompts
- `out/analysis_reports/f_sales_history_validation_latest.csv`
  - `3433` rows
  - includes chart month points, completed/current/future split, replay demand basis, break-even, and estimated monthly profit
- `out/analysis_reports/f_full_capture_monthly_points_latest.csv`
  - `363` rows
- `out/analysis_reports/f_full_capture_normalized_facts_latest.csv`
  - `30` rows
- `out/analysis_reports/f_live_asin_validation_pack_latest.csv`
  - `12` rows

### F already consumes some H outputs
- `scripts/flows/F/_source_contracts.py` declares `listing_offer_snapshot_latest` as an H-owned source contract.
- `scripts/flows/F/F071_build_backtest_input_view.py` loads that H listing snapshot into the backtest input view.
- `scripts/flows/F/F072_run_backtest_replay.py` already models:
  - competition scenario
  - share caps
  - demand basis source
  - price-qualified units
  - estimated units and profit
- `scripts/flows/F/F073_build_backtest_summary.py` already emits:
  - expected units next 30 days
  - expected profit next 30 days
  - decision state
  - sellable ceiling zone
  - Amazon risk
  - compression risk
  - share-assumption basis

## What F does not yet do
- It does not learn from:
  - actual H repricer outcomes
  - actual undercut pressure
  - real seller-count behavior after price moves
  - actual post-buy sales vs estimate by factor bucket
- It still relies on static or replayed assumptions where live H evidence should eventually take over.
- Its current live backtest owner files are empty as of `2026-04-14T15:19:33Z`, so the current truth for this ticket is in the analysis reports, not those empty live files.

## Cross-system gap
- There is no shared learning mart joining:
  - H market context
  - H decision and write result
  - later buy box/share outcome
  - actual sales/profit outcome
  - F estimate at buy time
  - F estimate error by factor
- That is the missing system.

## What the next task should build

### 1) A joined fact layer
- Build one-off outputs first:
  - `hf_learning_market_facts_latest.csv`
  - `hf_learning_action_outcomes_latest.csv`
  - `hf_learning_alignment_30d_latest.csv`
  - `hf_learning_factor_impacts_latest.csv`
- These should not change live logic yet.

### 2) Operator reports
- Show by SKU and by tactic family:
  - undercut frequency
  - time-to-rival-move
  - share-hold vs match vs reset outcomes
  - actual sales vs expected sales
  - margin effect
  - factor buckets behind misses

### 3) Monthly alignment
- Create a repeatable 30-day alignment pack like F already does for scrape validation, but driven by:
  - H live competition facts
  - F expected units/profit
  - our actual units/profit
  - new discrepancy tags

### 4) Shadow calibration into F
- Feed factor-level truth back into F scoring, but only in shadow mode first.
- Example factor families:
  - seller-count pressure
  - Amazon pressure
  - delivery parity
  - undercut reaction lag
  - price-ladder depth
  - repeated floor-clamp behavior
  - estimate-vs-actual demand drift

### 5) Controlled H experiments after the evidence layer exists
- only after joined reporting is truthful
- compare tactic families such as:
  - single-rival reset
  - multi-seller ladder cap
  - share hold
  - suppression reactivation
  - controlled exit

## Recommended order
1. Build read-only joined evidence.
2. Add schema checks and health checks for the new outputs.
3. Build operator reports and discrepancy outputs.
4. Feed shadow calibration factors into F.
5. Only then use the evidence to change live H strategy.

## Current blockers to respect
- H strategy warnings remain open and should stay visible.
- The global aggregate checklist has an older contradictory H fail and should not be used as fresh scoped proof for this ticket.
- F live backtest files are empty, so Batch 001 must treat the analysis packs as the current baseline evidence and decide the correct owner path before any loop promotion.
