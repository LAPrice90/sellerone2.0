# Master Working Plan - Competition Intelligence and Delivery Value Engine

## Purpose of this file
- This is the single source-of-truth strategy file.
- It combines the original master plan with your captured priority ideas from `chatgpt_log.md`.
- New chats should start here first.

## Current problem in plain language
- The system collects a lot of data, but not all of it is decision-grade.
- Raw lowest price is often not the right anchor.
- We must separate market-with-us and market-without-us.
- Delivery promise has real conversion value and must be priced in GBP terms.
- Seller behavior must be modeled at seller level, not just SKU level.
- Same seller can appear multiple times on one listing and must not be collapsed into one row.

## Non-negotiable principles
- Data first, thresholds later.
- Root-cause fixes at source, never downstream masking.
- Market-without-us is mandatory in all competitive analysis.
- Buy Box relevance beats absolute low outlier pricing.
- Delivery value must be converted into explicit GBP penalties.
- Aggression is a controlled state, not default behavior.
- Every new feature adds health checks and proof outputs.

## What must never be ignored

### 1) Market without us
- If we hold Buy Box, still compute who wins without us.
- Required signals:
- `buy_box_price_without_us`
- `best_rival_effective_price_without_us`

### 2) Delivery date has monetary value
- Price-only comparison is incomplete.
- Decision must use effective price:
- `effective_price = landed_price + delivery_penalty`
- This prevents false conclusions where higher margin price causes sales collapse due to slower delivery.

### 11) Buy Box eligibility signals for ceiling discovery
- We must separate "can win Buy Box" from "lowest visible listing price".
- Add daily eligibility signals:
- `Featured Offer Expected Price (FOEP)`
- `CompetitivePriceThreshold`
- These signals feed the SKU ceiling model and reduce blind ceiling guesses.
- FOEP and threshold are intelligence inputs, not autonomous price-write triggers.

### 3) Seller behavior intelligence
- 10 sellers does not mean 10 true competitors.
- We must identify core competitors and aggressors.
- A seller can have multiple live offers on the same listing (different delivery promise, fulfilment route, or promo state).
- Keep seller profile and offer instance data separate so no overwrite happens.
- Required seller outputs:
- `seller_profile_state` (aggressor/follower/passive/sporadic)
- `seller_floor_estimate_gbp`
- `seller_ceiling_estimate_gbp`
- `seller_reaction_score`

### 8) Duplicate seller offers must be instance-safe
- One seller can appear more than once on the same SKU at the same timestamp.
- Never dedupe by `seller_id` only.
- Store each row as a distinct offer instance.
- Build strategy at two levels:
- seller level for long-term memory and floor behavior
- offer-instance level for live threat selection
- Daily decision rule:
- Keep all instances for market truth.
- For each seller, select that seller's strongest current threat instance.
- Run per-seller game logic against the strongest instance.

### 4) Controlled nuclear mode
- Manual strategy proved this can work for specific high-value listings.
- This is allowed only as a guarded state with strict criteria:
- high profit potential
- high aggressor confidence
- time-boxed duration
- ROI floor never breached
- explicit reason codes and expiry

### 5) Data before thresholds
- Do not set static thresholds upfront.
- Gather real outcomes first.
- Convert manual judgment into rules after observed evidence stabilizes.

### 6) Track us as a player
- We must model our own behavior in the same event stream:
- our moves
- rival reactions
- outcome lag
- conversion and profit impact

### 7) Seller of Interest trigger and strategy memory
- Build seller-level profiles only when a seller is relevant, not for every seller forever.
- A seller becomes a Seller of Interest if any trigger is true:
- they take Buy Box on a tracked SKU
- they stay within a configurable range of Buy Box for a minimum number of observations
- they trigger repeated price reactions in a rolling window
- Once flagged, keep a reusable strategy memory for that seller:
- observed floor/ceiling band
- aggression and reaction profile
- delivery posture pattern
- prior successful and failed response states against that seller
- At decision time, choose the highest current threat seller for that SKU and apply seller-specific strategy first.

### 9) Tiered seller model (always-on basic tracking)
- Keep every seen seller in the system, but not every seller gets full strategy modeling.
- Two tiers:
- Tier 1 `basic_profile` (all sellers):
- purpose: continuity and fallback when market structure changes
- fields: typical price band, typical delivery days, fulfilment mix, estimated beat delta
- Tier 2 `seller_of_interest` (high-impact sellers):
- purpose: full strategy memory and game-level optimization
- fields: floor/ceiling, reaction speed, aggression profile, outcome history
- Promotion rule:
- if active Tier 2 sellers for a SKU fall below minimum coverage, promote the highest-threat Tier 1 seller.
- Demotion rule:
- if a Tier 2 seller has no qualifying activity for a full cooling window, demote to Tier 1 but keep history.

### 10) Seller tier categorization rules
- Step A - Eligibility gate (must pass at least one):
- within configured percent band of Buy Box effective price
- wins Buy Box at least once in lookback window
- appears in top-N effective offers at least M times
- Step B - Activity gate (must pass at least one):
- changed price at least K times in lookback window
- changed delivery promise at least K times in lookback window
- associated with observed Buy Box/share loss event for us
- Classification outputs:
- pass A and pass B -> Tier 2 `seller_of_interest`
- pass A only -> Tier 1 `watchlist_basic`
- fail A and fail B -> Tier 1 `background_basic`
- Tier changes must be timestamped and reason-coded for auditability.

## Core decision model

### 1) Market without us calculation
For each SKU and timestamp:
- remove our seller row(s)
- find best rival using effective price
- publish without-us snapshot fields

### 2) Effective price model
Required dimensions:
- `listing_price_gbp`
- `shipping_price_gbp`
- `landed_price_gbp = listing_price_gbp + shipping_price_gbp`
- `delivery_days`
- `delivery_gap_days_vs_fastest`
- `delivery_value_penalty_gbp`
- `effective_price_gbp = landed_price_gbp + delivery_value_penalty_gbp`

### 4) Eligibility ceiling model (daily refresh)
Required dimensions:
- `foep_price_gbp`
- `competitive_price_threshold_gbp`
- `buy_box_eligibility_ceiling_gbp`
- `eligibility_confidence`
- `eligibility_last_refresh_utc`

Default logic:
- ceiling candidate starts at FOEP when present
- clamp candidate by CompetitivePriceThreshold when lower
- pass final candidate through Head floor and ROI feasibility gate

### 3) Action scoring
Minimum score inputs:
- `our_effective_price_gbp`
- `best_rival_effective_price_gbp_without_us`
- `effective_gap_gbp`
- `expected_profit_per_unit_gbp`
- `expected_units_if_competitive`
- `expected_profit_per_day_if_competitive`
- `seller_aggression_score`
- `stock_feasibility`

States:
- cooperate
- hold
- probe
- pressure
- defensive
- hibernate

## Game Funnel Decision Technique (new core method)

### Concept
- Treat each SKU x seller pair as a separate "game of chess".
- Each game asks one question:
- "What price do we need to win enough share from this seller under current conditions?"
- The worker solves many games, then selects one final executable answer.

### Per-seller game output
For each relevant seller `s` on a SKU, produce:
- `required_price_to_win_s`
- `required_price_confidence_s`
- `seller_floor_estimate_s`
- `seller_floor_confidence_s`
- `delivery_adjusted_gap_s`
- `expected_share_gain_s`
- `reason_codes_s`

### Funnel aggregation
- Step 1: compute all per-seller required prices.
- Step 2: choose coverage policy:
- win all relevant sellers, or
- win core-threat subset only (from Seller of Interest ranking).
- Step 3: aggregate to one candidate target price.

Default aggregation policy:
- For "win all selected games", candidate target is the minimum required winning price across selected sellers.

### Feasibility gate (must pass before execution)
- candidate target is checked against:
- our margin floor and break-even rules
- stock posture rules
- risk and guardrail policy
- If candidate fails feasibility, do not force execution.
- Escalate to Supervisor or Head state:
- hold/defensive/hibernate, or
- open cost-side actions to improve capability.

## Buy Box delta learning loop (seller specific)

### Why this exists
- Visible rival price is not always the true winning condition.
- Amazon funded temporary discounts and delivery advantages can hide the real Buy Box threshold.
- We therefore learn the winning delta from outcomes, not from one static visible price.

### Strategy unit
- Learning key is `SKU + seller_id`.
- Track each seller independently on the same SKU.
- Store daily learned values plus confidence and timestamp.

### Core method
- Step 1 - Start with an estimated delta versus rival visible price.
- Step 2 - Test in fixed time windows (default 15 minutes) and observe Buy Box owner after each move.
- Step 3 - If we do not win Buy Box, move downward in controlled steps until first win.
- Step 4 - Once win found, probe upward in small increments to find the highest still-winning delta.
- Step 5 - Save two bounds:
- `highest_delta_win_gbp`
- `lowest_delta_loss_gbp`
- Step 6 - Binary narrow between the two bounds until no practical untested gap remains.
- Step 7 - Use the learned winning delta for live follow actions during the day.
- Step 8 - Re-test once daily, or immediately if win rate drops or rival behavior changes.

### Moving target handling
- Rival may change price during our test sequence.
- Do not reset blindly.
- Re-anchor to current rival price and continue bracket narrowing with updated bounds.
- Keep latest tested state:
- current rival price
- current our price
- last winning delta
- last losing delta

### Invisible sale handling
- If observed outcomes conflict with visible price expectations repeatedly, mark seller as `promo_suspected`.
- In `promo_suspected` state:
- use smaller probe steps
- use faster recheck cadence
- keep tighter confidence thresholds before locking delta

### Required data fields
- `delta_test_id`
- `seller_id`
- `sku`
- `rival_visible_price_gbp`
- `our_test_price_gbp`
- `observed_buy_box_owner`
- `observed_buy_box_price_gbp`
- `delta_vs_rival_gbp`
- `test_result` (`win` or `loss`)
- `highest_delta_win_gbp`
- `lowest_delta_loss_gbp`
- `delta_confidence`
- `promo_suspected_flag`
- `test_window_minutes`
- `captured_utc`

### Operational guardrails
- Respect Head floor and margin guards at all times.
- Cap total daily downward movement per SKU.
- Hard stop on repeated unstable outcomes.
- Escalate to Supervisor state change if confidence remains low.

## Official staff roles (locked)

### Head (portfolio owner)
- Sets global boundaries: margin floor, risk limits, and where to fight or exit.
- Approves or rejects major escalation paths when capability changes are needed.
- Reviews broad outcomes on lower frequency cadence.

### Supervisor (SKU strategy owner)
- Decides if a listing is worth fighting for within Head boundaries.
- Chooses SKU state and strategy path each day.
- If worth fighting and current floor is too high, Supervisor can trigger capability actions:
- FBA fee optimization (valid remeasure/reclass path)
- supplier discount negotiation
- bulk purchasing leverage
- alternate supplier sourcing
- direct supplier relationship improvements
- If not worth fighting, Supervisor can reduce aggression level and redeploy effort.

### Executioner (live operator)
- Plays each seller game using current profile data.
- Produces required prices and one candidate target.
- Executes approved moves and records immediate outcome evidence.

## Operational logic model (from live story)

### Control hierarchy
- Head controls boundaries and intent per SKU.
- Supervisor controls strategy state and check frequency per SKU.
- Executioner controls live actions only within approved boundaries and state rules.

### Cycle separation rule (official)
- Pricing runtime must be a dedicated loop process (H pricing cycle), separate from A and B cycles.
- A cycle is for data build and health validation.
- B cycle is for order/financial operational flow.
- H pricing cycle runs Head, Supervisor, and Executioner cadences without being embedded into A/B loop code.

### Default role cadence (official)
- Head: every 24 hours (morning cycle).
- Supervisor: every 4 hours.
- Executioner: every 0.25 hours (15 minutes) baseline.
- Trigger overrides can force immediate checks between scheduled cycles.

### Boundary model per SKU (set by Head daily)
- `hard_floor_price_gbp` (cannot go below)
- `soft_floor_price_gbp` (normal lower bound for the day)
- `target_roi_band_pct`
- `today_intent` (`defend_margin`, `harvest_sales`, `floor_discovery`, `wait_out`, `recover_margin`)
- `api_budget_tier` (`low`, `medium`, `high`)

### State machine per SKU (set by Supervisor)
- `parked`
- `monitor`
- `duel`
- `floor_discovery`
- `wait_out`
- `recovery`

### Default check cadence by state
- `parked`: event-driven only plus heartbeat every 4 to 8 hours
- `monitor`: every 2 to 4 hours
- `duel`: every 15 to 30 minutes
- `floor_discovery`: every 15 minutes with guarded step ladder
- `wait_out`: every 30 to 60 minutes
- `recovery`: every 30 to 120 minutes depending on stability

### Trigger overrides (force immediate check)
- Buy Box loss event
- rival price move beyond threshold
- rival delivery promise improves to same-day or next-day
- known aggressor re-entry detected
- our stock posture crosses risk threshold

### Pricing action permissions
- Head may change `hard_floor_price_gbp`, `soft_floor_price_gbp`, and `today_intent`.
- Supervisor may change state, cadence, and move ladder settings.
- Supervisor may tighten cadence or slow cadence, but cannot breach Head floors.
- Executioner may execute only approved move types and approved price corridor.

### Move ladder for floor discovery
- Use configurable step size by band (example: 0.50 GBP every 15 minutes).
- Stop immediately at hard floor or break-even rule.
- When rival follows repeatedly, estimate floor confidence.
- Once rival floor is estimated, switch from discovery to wait-out.

### Wait-out play
- If rival is trapped near low ROI, avoid unnecessary undercut churn.
- Sit at approved holding position (for example one penny above or below based on strategy).
- Focus on time pressure and stock pressure, not constant repricing.
- Continue monitoring for rival stockout, delivery deterioration, or retreat.

### Recovery play after aggressor exits
- Raise toward recovery corridor in controlled steps.
- Re-anchor to next active seller game from stored strategy memory.
- Restore margin before resuming normal monitor cadence.

### Daily narrative loop (formalized)
- Morning Head review sets boundaries and intent.
- Supervisor maps each SKU into a state and cadence plan.
- Executioner runs the loop all day with trigger overrides.
- End-of-day outcome is fed back into seller memory, floor confidence, and next-day intent.

### Guardrails (mandatory)
- No action below hard floor.
- No uncontrolled repeated drops without stop conditions.
- Every aggressive ladder must include max daily total cut, cooldown, and abort conditions.
- Every executed action must log reason code, previous price, new price, and immediate outcome.

## Seller floor handling rules
- Floor is an estimate, not a constant.
- Detect floor from repeated chase-stop behavior.
- Store floor with confidence and recency.
- Assume floors can move during conflict.
- Re-estimate continuously with fresh observations.

## Delivery value model (how we calculate X GBP)
- No single global constant.
- Learn by SKU or cluster from observed outcomes.

Method:
1. Find periods with stable price but changing delivery gap.
2. Measure Buy Box share or sales share impact.
3. Fit a simple delivery-gap response curve.
4. Convert conversion loss into GBP equivalent.
5. Store `delivery_value_per_day_gbp` and confidence.

Starter shape:
- day 0 gap: 0.00
- day 1 gap: p1
- day 2 gap: p2
- day 3+ gap: p3 capped

## Data contract

### Listing offer level
- timestamp_utc
- asof_date
- marketplace
- sku
- asin
- offer_instance_id
- observation_rank
- seller_id
- seller_name_raw
- seller_id_canonical
- fulfilment_channel
- is_prime
- listing_price_gbp
- shipping_price_gbp
- landed_price_gbp
- min_delivery_days
- max_delivery_days
- delivery_range_days

### Derived market context
- buy_box_price_raw_gross
- buy_box_price_used_gross
- buy_box_price_without_us_gross
- buy_box_suppressed_flag
- our_buy_box_win_rate_7d
- our_buy_box_win_rate_30d
- rival_buy_box_rotation_est_7d
- best_rival_landed_price_without_us
- best_rival_effective_price_without_us
- lowest_fba_landed_price
- lowest_fbm_landed_price
- highest_landed_price
- median_landed_price
- offer_count_trend_7d
- offer_count_trend_30d
- seller_churn_rate_30d
- sales_rank_primary
- sales_rank_category
- sales_rank_bucket
- sales_rank_trend_7d
- sales_rank_trend_30d
- sales_rank_volatility_30d
- product_rating_value
- product_rating_count
- product_rating_velocity_30d
- seasonality_index_month

### Economics and action context
- break_even_price_gbp
- min_price_floor_gbp
- max_price_ceiling_gbp
- current_fee_tier
- fee_jump_risk_flag
- expected_fee_if_price_changes_gbp
- roi_at_our_price_pct
- roi_at_rival_price_pct
- expected_profit_per_day_if_competitive
- expected_units_per_day_from_rank
- expected_units_per_day_confidence
- expected_refund_rate_pct
- expected_return_impact_gbp
- unit_session_percent_7d
- unit_session_percent_30d
- keyword_rank_core_terms
- state_recommendation
- reason_codes
- confidence
- expiry_utc

### Seller of Interest profile
- seller_id
- seller_id_canonical
- first_seen_utc
- last_seen_utc
- seller_tier
- seller_tier_reason_code
- seller_tier_changed_utc
- seller_profile_state
- seller_aggression_score
- seller_reaction_lag_minutes_est
- seller_floor_estimate_gbp
- seller_ceiling_estimate_gbp
- seller_delivery_posture
- seller_feedback_score_pct
- seller_feedback_count
- seller_feedback_trend_30d
- seller_stockout_events_30d
- seller_interest_trigger_reason
- seller_interest_active_flag
- seller_strategy_memory_version

### Basic seller profile (all sellers)
- seller_id
- seller_id_canonical
- first_seen_utc
- last_seen_utc
- seller_tier
- typical_price_low_gbp
- typical_price_high_gbp
- typical_min_delivery_days
- typical_max_delivery_days
- fulfilment_mix_fba_share
- fulfilment_mix_fbm_share
- estimated_beat_delta_gbp
- observed_offer_count_lookback
- last_seen_on_tracked_sku_utc

### Offer instance handling rules
- Uniqueness key for raw offer rows:
- `timestamp_utc + sku + seller_id_canonical + fulfilment_channel + landed_price_gbp + min_delivery_days + max_delivery_days`
- If two rows are still identical after key build, keep both and assign different `offer_instance_id` values with a stable tie-break rank.
- Seller profile aggregation never deletes instance rows.
- Seller floor estimation uses seller-level history, while live threat selection uses instance-level records.
- Offer attributes required for quality normalization:
- `promo_flag`
- `coupon_flag`
- `unit_price_gbp`
- `pack_size_normalized_units`
- `stock_estimate_units`
- `stock_estimate_confidence`

## Phase plan (execution direction)

### Phase 0 - Safe Mode repricer (first 7 days)
- Enable live execution with strict guardrails and no battle plans.
- Purpose: start collecting real behavior data immediately while limiting downside risk.
- Mode rules:
- follow Buy Box safely within boundaries
- no floor discovery ladders
- no aggressive duel sequences
- no rapid repeated down moves
- Required controls:
- hard floor and break-even protection
- max move size per cycle
- max total down move per SKU per day
- cooldown between moves
- kill switch and anomaly stop

### Phase 1 - Signal correction and pilot-only live testing
- Landed price default for competition envelopes.
- Keep listing and shipping fields for transparency.
- Add without-us outputs.
- Run Head/Supervisor/Executioner decision outputs with live pilot actions.
- Use controlled live repricing writes on pilot SKU to measure real market response.
- Compare planned vs executed vs outcome.

### Phase 2 - Blind-spot bridge (controlled probes on pilot only)
- Continue controlled probes on pilot SKU only until behavior confidence is sufficient.
- Use bounded probe types only:
- hold test
- small step-down
- small step-up recovery
- timed no-change window
- Goal: estimate reaction lag, seller floor hints, and aggressor behavior with confidence.

### Phase 3 - Competitor profile build-out
- Build seller floor/ceiling/aggression/reaction features.
- Identify core competitors and follower chains.
- Implement tier categorization and automatic promotion/demotion.

### Phase 4 - Decision layer to assisted execution
- Use effective rival price and delivery-adjusted value.
- Output state recommendations with expiry and reasons.
- Promote from advisory to assisted execution only where evidence quality is sufficient.

### Phase 5 - Scaled execution with guardrails
- Expand strategy-first execution by SKU cohorts.
- Keep no-breach guardrails and rollback path active.
- No autonomous aggressive mode without staged proof history.

Expansion gate rule:
- Do not add additional SKUs until the pilot proves full 3-role workflow end-to-end with live market tests, stable guardrail compliance, and explicit approval.

## Proof requirements
- Row-count and reconciliation proof for each new output.
- At least one worked SKU case showing:
- rival listing/shipping/landed
- delivery penalty
- effective comparison
- sales rank context and trend
- buy box win-rate context
- seller churn and offer-count trend context
- final state and reason
- Health checks for all new outputs and constraints.
- No hidden overrides.

## Re-entry memory (leave and return)
- When we come off a listing, keep a re-entry baseline:
- sales rank at exit
- demand trend at exit
- competitive density at exit
- last known seller floors and delivery posture
- On return, calculate deltas vs exit baseline before setting first price action.
- Rank interpretation rule:
- if sales rank worsens materially between exit and return (example: 5000 to 12000 in same category), reduce expected unit forecast and use a defensive opening strategy.
- rank-driven forecast changes must include context checks:
- category unchanged
- no major price regime shift
- no temporary stockout distortion
- seasonality difference between comparison months

## Things to avoid
- Price-only logic.
- Using `lowest_offer_price` as primary action anchor.
- Treating all sellers as equally relevant.
- Permanent aggression states.
- Automation before advisory logic is validated.
- Forgetting known seller behavior when that seller reappears on a listing.

## Governance and workflow
- Keep this file as the strategic master.
- Keep mini phase plans for implementation detail.
- All new ideas must be merged into this file, not scattered across chats.
- Supersede old assumptions with dated notes, never silent deletion.

## Research backlog (for ChatGPT deep research)
- Delivery promise impact on conversion and Buy Box outcomes.
- Buy Box drivers beyond price.
- Repeated-game and adversarial pricing behavior.
- Floor/ceiling detection methods under noisy observations.
- Safe probe and escalation design patterns.
- Non-Amazon analogs that transfer to marketplace pricing.

## Open questions
- Final formula family for delivery value by SKU.
- Best proxy for Buy Box share when direct share is unavailable.
- Required persistence window for aggressor reclassification.
- Minimum evidence threshold before enabling pressure state.
- Final default trigger thresholds for Seller of Interest activation and deactivation.
- Stock estimate confidence threshold before stock signals affect pricing state.
- Best source and cadence for keyword rank tracking.
- Minimum sample size for using rating velocity in decision state.

## Handoff instructions for fresh chats
- Read this file first.
- Add new ideas here before planning execution.
- Map each implementation step back to a section in this file.
- Do not restart strategy design from zero.

## New listing activation and dual-profile model (official)
- Use two profiles at the same time:
- SKU profile (listing-level rules):
- mode (`launch`, `low_competition`, `active_competition`, `defensive`)
- hard floor and soft floor
- competitive ceiling price (max realistic sell price)
- target ROI band and cadence policy
- SKU-seller profile (opponent-level rules):
- one profile per `sku + seller_id`
- seller floor estimate
- aggression state
- reaction speed
- delivery pressure pattern
- threat tier

### New listing start rule
- Do not start in aggressive competition mode by default.
- Start in `launch` mode:
- enforce floor and ceiling
- collect seller behavior
- only promote sellers to active game strategy after evidence threshold is met
- ignore random low-threat noise sellers in execution decisions
- keep them in background tracking only

### Price decision clamp rule (mandatory)
- Worker computes two independent outputs each cycle:
- low-side price from seller game funnel (`required_price_to_win_selected_sellers`)
- high-side price from SKU-level competitive ceiling (`competitive_ceiling_price`)
- Final executable target must be clamped:
- final target cannot go below floor and cannot go above ceiling
- if seller game requires higher than ceiling, cap at ceiling
- if seller game requires lower than floor, hold floor and switch state (defensive or wait)

### Low/no-competition handling
- Low/no-competition is not "ignore pricing".
- It is "maximize realistic margin within competitive ceiling".
- Behavior:
- reduce execution frequency
- edge price upward toward ceiling in controlled increments
- keep instant trigger for re-entry of known aggressor sellers
- if aggressor returns, resume active seller-game mode immediately

### Temporary ceiling source rule
- Until automated ceiling logic is approved, use manual ceiling value from BBP max sold price.
- Store this ceiling per SKU as the temporary official ceiling input.
- Mark every decision that uses this temporary ceiling with a reason code.
