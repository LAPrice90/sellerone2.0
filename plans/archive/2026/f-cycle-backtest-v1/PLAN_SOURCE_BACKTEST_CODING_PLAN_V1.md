# F Cycle Backtest Coding Plan V1

## Purpose

This document turns the research notes into a practical v1 build plan.

It is intentionally limited to v1 only.

The aim is:
- build a backtest that replays price history as the repricer would experience it
- estimate profit using existing F and E demand signals
- show risk and stability without pretending the model knows exact future sales
- surface the result inside the restock workflow

## V1 Outcome

By the end of v1, the system should be able to answer:

- if we had bought this ASIN during past periods, would our policy likely have made enough money overall?
- how often would the listing have gone into hold or sell-off behavior?
- how much capital would likely have been tied up?
- how much of the listing demand should we assume belongs to us under simple competition scenarios?

The result should be:
- profit-first
- repricer-aware
- risk-explained
- simple enough to trust

## V1 Non-Goals

Do not build these in v1:

- exact child-level demand attribution
- exact seller-by-seller market share
- optimisation or auto-tuning
- explicit inflation modelling
- advanced UI design work

## Existing Repo Inputs To Reuse

### Core raw chart history

Use:
- [feeder_legacy_chart_daily_raw_live.csv](/c:/Users/Luke/Desktop/SellerOne%202.0/out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv)

Owned by F contract:
- [scripts/flows/F/_schemas.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/F/_schemas.py)

Current useful fields:
- `asin`
- `day`
- `amazon_price_raw`
- `fba_price_raw`
- `fbm_price_raw`
- `buy_box_price_raw`
- `bsr_raw`
- `price_chosen_processed`
- `phase_processed`

### Existing demand / sales signal

Use:
- [sku_sales_velocity.csv](/c:/Users/Luke/Desktop/SellerOne%202.0/out/sku_sales_velocity.csv)

Built by:
- [E001_build_sales_velocity.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/E/E001_build_sales_velocity.py)

Primary fields already available:
- `sku`
- `window_days`
- `units_sold`
- `velocity_units_per_day`

### Current restock UI and contracts

Restock source and UI already exist here:
- [scripts/flows/O/_schemas.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/O/_schemas.py)
- [scripts/flows/O/O001_build_restock_source_view.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/O/O001_build_restock_source_view.py)
- [scripts/flows/O/O400_operator_ui.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/O/O400_operator_ui.py)

### Current repricer ownership

The live repricer remains H flow:
- [project_control/REPRICER_RUNTIME_CONTRACT.md](/c:/Users/Luke/Desktop/SellerOne%202.0/project_control/REPRICER_RUNTIME_CONTRACT.md)

V1 backtest does not alter H runtime.
It simulates policy behavior from historical data.

## V1 Build Shape

Keep the first version to 4 layers:

1. policy layer
2. input-prep layer
3. replay layer
4. summary and UI layer

## Recommended New Files

### F flow

Add these new F builders:

- `scripts/flows/F/F070_build_backtest_policy_snapshot.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`

### Optional O flow integration

Modify existing O flow instead of inventing a separate UI subsystem:

- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O400_operator_ui.py`

## Recommended New Output Files

Add new F contracts for:

- `out/systems/F/live/feeder_backtest_policy_live.csv`
- `out/systems/F/live/feeder_backtest_input_view_live.csv`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/live/feeder_backtest_health.csv`

Purpose of each:

- `feeder_backtest_policy_live.csv`
  - one active v1 policy row

- `feeder_backtest_input_view_live.csv`
  - one row per ASIN with prepared replay inputs and confidence flags

- `feeder_backtest_replay_daily_live.csv`
  - replay output per ASIN per day

- `feeder_backtest_summary_live.csv`
  - one row per ASIN with final result metrics used by O and operator review

- `feeder_backtest_health.csv`
  - F-scoped health checks for the new backtest outputs

## Execution Lock - Exact V1 Contracts

This section locks the exact first-pass file names and columns so Codex can implement without guessing.

### 1) `feeder_backtest_policy_live.csv`

Path:
- `out/systems/F/live/feeder_backtest_policy_live.csv`

Required columns:
- `observed_utc`
- `policy_id`
- `policy_version`
- `policy_status`
- `minimum_expected_profit_gbp`
- `entry_target_roi_pct`
- `working_floor_roi_pct`
- `exit_floor_roi_pct`
- `emergency_floor_roi_pct`
- `recency_weight_30d`
- `recency_weight_90d`
- `recency_weight_180d`
- `recency_weight_365d`
- `ceiling_warn_ratio_30d`
- `ceiling_red_ratio_30d`
- `ceiling_extreme_ratio_30d`
- `shock_trigger_pct_1d`
- `shared_sales_default_pct`

Optional columns:
- `policy_source`
- `notes`

### 2) `feeder_backtest_input_view_live.csv`

Path:
- `out/systems/F/live/feeder_backtest_input_view_live.csv`

Grain:
- one row per `seller_sku + asin + policy_id`

Required columns:
- `observed_utc`
- `policy_id`
- `seller_sku`
- `asin`
- `supplier_code`
- `supplier_name`
- `mapping_status`
- `input_status`
- `input_reason_codes`
- `history_days`
- `paired_buy_box_bsr_days`
- `paired_fba_bsr_days`
- `buy_box_coverage_share`
- `amazon_presence_share_30d`
- `amazon_presence_share_90d`
- `price_median_30d_gbp`
- `price_median_90d_gbp`
- `price_median_180d_gbp`
- `price_median_365d_gbp`
- `bsr_median_30d`
- `bsr_median_90d`
- `base_velocity_30d_units_per_day`
- `current_supplier_buy_cost_gbp`
- `break_even_price_gbp`
- `market_price_gbp`
- `seasonality_state`
- `history_confidence`
- `manual_review_flag`

Optional columns:
- `title`
- `expected_refund_cost_per_unit_gbp`
- `roi_at_market_price_pct`
- `notes`

### 3) `feeder_backtest_replay_daily_live.csv`

Path:
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv`

Grain:
- one row per `seller_sku + asin + day + policy_id`

Required columns:
- `observed_utc`
- `policy_id`
- `seller_sku`
- `asin`
- `day`
- `replay_status`
- `competition_scenario`
- `replay_mode`
- `price_zone`
- `demand_state`
- `simulated_price_gbp`
- `buy_box_price_gbp`
- `amazon_price_gbp`
- `lowest_fba_price_gbp`
- `lowest_fbm_price_gbp`
- `bsr_value`
- `sales_share_pct`
- `seasonality_multiplier`
- `estimated_listing_units`
- `estimated_units_ours`
- `estimated_profit_gbp`
- `failure_event_flag`
- `manual_review_flag`

Optional columns:
- `reason_codes`
- `roi_band`
- `ceiling_confidence`
- `notes`

### 4) `feeder_backtest_summary_live.csv`

Path:
- `out/systems/F/live/feeder_backtest_summary_live.csv`

Grain:
- one row per `seller_sku + asin + policy_id`

Required columns:
- `observed_utc`
- `policy_id`
- `seller_sku`
- `asin`
- `summary_status`
- `summary_reason_codes`
- `history_confidence`
- `market_viability_score`
- `exit_risk_score`
- `estimated_total_profit_gbp`
- `estimated_monthly_profit_gbp`
- `capital_lockup_days`
- `sellable_ceiling_zone`
- `amazon_risk_level`
- `compression_risk_level`
- `recommendation`
- `manual_review_reason`
- `failure_event_count`
- `longest_failure_streak_days`
- `time_normal_sell_days`
- `time_hold_wait_days`
- `time_selloff_days`
- `share_assumption_basis`

Optional columns:
- `recovery_rate`
- `seasonality_flag`
- `notes`

### 5) `feeder_backtest_health.csv`

Path:
- `out/systems/F/live/feeder_backtest_health.csv`

Required columns:
- `check`
- `status`
- `value`
- `notes`
- `observed_utc`

Optional columns:
- `source_path`

## Policy Storage For V1

Store one active policy profile in:
- `feeder_backtest_policy_live.csv`

Why:
- editable later from UI
- not hard-coded in scripts
- simple enough for v1

Keep only these editable controls in v1:

- `minimum_expected_profit`
- `entry_target_roi`
- `working_floor_roi`
- `exit_floor_roi`
- `emergency_floor_roi`

Keep these as system defaults in v1:

- recency weights
- confidence gates
- ceiling stretch ratios
- Amazon memory logic
- seasonality handling
- provisional share assumptions

## Execution Lock - Exact Join Keys

This section locks the joins so Codex does not improvise them during implementation.

### Join 1 - Raw F history to prepared ASIN history

Source:
- `feeder_legacy_chart_daily_raw_live.csv`

Key:
- `asin`

Rule:
- group raw chart rows by `asin + day`
- keep one prepared daily market row per ASIN-day before any SKU expansion

### Join 2 - ASIN history to product identity

Source:
- `out/product_db_preview.csv`

Keys:
- `asin` exact match

Rule:
- expand one ASIN history row to one or more `seller_sku` rows when `product_db_preview` contains that ASIN
- current repo evidence shows this is mostly clean and only a small number of ASINs map to multiple SKUs

`mapping_status` values for v1:
- `unique_asin_match`
- `multi_sku_asin_match`
- `no_product_db_match`

V1 behavior:
- `unique_asin_match` = ready to continue
- `multi_sku_asin_match` = continue, but mark reduced confidence / manual-review-cap
- `no_product_db_match` = keep F output row, but no O merge path

### Join 3 - Demand signal

Source:
- `out/sku_sales_velocity.csv`

Keys:
- `seller_sku` from product map
- `sku` from E output

Rule:
- join on `seller_sku = sku`
- use the 30-day row as the primary demand row
- where multiple window rows exist, prefer `window_days = 30`

### Join 4 - Economics context

Source:
- `out/sku_performance_summary.csv`

Keys:
- `seller_sku`
- `sku`

Rule:
- join on `seller_sku = sku`
- use for:
  - `expected_refund_cost_per_unit_gbp`
  - `break_even_price_gbp`
  - ROI context fields

### Join 5 - Optional live market context

Source:
- `out/listing_offer_snapshot_latest.csv`

Keys:
- `seller_sku`
- `asin`

Rule:
- use this only as current-context support
- do not let it replace the historical replay inputs

### Join 6 - O source view merge

Target:
- `O001_build_restock_source_view.py`

Primary merge key:
- `seller_sku`

Cross-check field:
- `asin`

V1 rule:
- merge backtest summary into O by `seller_sku`
- verify `asin` also matches when present
- do not use `asin`-only merge inside O in v1

Reason:
- `seller_sku` is the safest operator-facing row key
- this avoids ambiguous duplication when one ASIN appears on several SKUs

## Input View Logic

`F071_build_backtest_input_view.py` should produce a clean prepared row per ASIN.

It should:
- load raw daily chart history from F
- group and sort by `asin` and `day`
- normalize daily prices to numeric values
- derive presence flags:
  - `amazon_present`
  - `fba_present`
  - `fbm_present`
  - `buy_box_present`
- derive ASIN-relative rolling baselines:
  - 30d median
  - 90d median
  - 180d median
  - 365d median where available
- derive BSR-relative features
- derive coverage and confidence fields
- attach the best available demand signal

V1 demand mapping rule:
- join to existing sales velocity where SKU mapping is available
- where SKU mapping is not available, keep confidence reduced and do not fake precision

Primary key direction for v1:
- backtest engine runs on `asin`
- O flow consumption can join on `asin`

## Replay Logic

`F072_run_backtest_replay.py` is the core engine.

It should replay each ASIN across historical days using the active policy.

### Daily replay steps

For each ASIN-day:

1. derive active market state
- current Buy Box price
- current Amazon price
- current FBA price
- current chosen processed price when available

2. derive price zone
- normal
- stretched
- probable ceiling breach

3. derive demand reaction state
- stable
- weakened
- deteriorating

4. derive competition scenario
- `solo_or_no_meaningful_competition`
- `sharing_with_amazon`
- `sharing_with_fba`
- `sharing_with_amazon_and_fba`

5. derive replay mode
- `normal_sell`
- `hold_wait`
- `sell_off`

6. estimate daily sales share
- if price-matching relevant competition, use provisional scenario share
- if above the active trading zone, reduce sales sharply

7. estimate daily units
- base listing demand
- adjusted by seasonality
- adjusted by scenario sales share

8. estimate daily financial result
- revenue
- unit margin
- daily profit

### Provisional v1 sales share rules

Use the simple placeholder logic already agreed:

- `solo_or_no_meaningful_competition` = `100%`
- `sharing_with_amazon` = `50%`
- `sharing_with_fba` = `50%`
- `sharing_with_amazon_and_fba` = `50%`

Important rule:
- only use shared-sales assumptions when price is matching the relevant market zone

### Repricer-aware failure logic

Do not fail a listing because one bad week existed.

Track instead:
- severity of bad periods
- duration of bad periods
- frequency of bad periods
- recovery after bad periods

The replay should decide when the simulated strategy would be in:
- normal selling
- hold / wait
- sell-off

## Seasonality Logic

Keep this simple in v1.

Use:
- recent price data for pricing truth
- same-season history for demand truth

V1 behavior:
- recent windows dominate price and competition
- same-season demand can reduce near-term sales expectation for seasonal products
- old seller pricing should not dominate current pricing logic

## Summary Logic

`F073_build_backtest_summary.py` should collapse the daily replay into one row per `seller_sku + asin + policy_id`.

Required summary outputs:

- `market_viability_score`
- `exit_risk_score`
- `estimated_total_profit_gbp`
- `estimated_monthly_profit_gbp`
- `capital_lockup_days`
- `sellable_ceiling_zone`
- `amazon_risk_level`
- `compression_risk_level`
- `history_confidence`
- `recommendation`

Also keep supporting evidence fields:

- `time_normal_sell_days`
- `time_hold_wait_days`
- `time_selloff_days`
- `failure_event_count`
- `longest_failure_streak_days`
- `recovery_rate`
- `share_assumption_basis`
- `seasonality_flag`
- `manual_review_reason`

## Recommendation Logic

Use the agreed v1 buckets:

- `score_input`
- `overlay_warning`
- `hard_fail`
- `no_grade_manual_review`

Working recommendation states:

- `Normal fit`
- `Managed fit`
- `Exit-only`
- `Avoid`
- `Manual review`

## O Flow Integration

Do not build a separate standalone UI first.

Integrate into the existing restock lane.

### Source view merge

Update:
- [O001_build_restock_source_view.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/O/O001_build_restock_source_view.py)

Add optional backtest columns from `feeder_backtest_summary_live.csv`:

- `backtest_policy_id`
- `backtest_history_confidence`
- `backtest_market_viability_score`
- `backtest_exit_risk_score`
- `backtest_estimated_total_profit_gbp`
- `backtest_estimated_monthly_profit_gbp`
- `backtest_capital_lockup_days`
- `backtest_sellable_ceiling_zone`
- `backtest_amazon_risk_level`
- `backtest_compression_risk_level`
- `backtest_recommendation`
- `backtest_manual_review_reason`

### Operator UI display

Update:
- [O400_operator_ui.py](/c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/O/O400_operator_ui.py)

Add a read-friendly backtest section inside the restock view.

V1 UI goal:
- show the result clearly
- do not build complex controls first

Recommended first display:
- monthly profit
- total profit
- viability score
- exit risk
- Amazon risk
- confidence
- recommendation

## Suggested Build Order

### Stage 1

Add new F output contracts and schemas.

Files:
- `scripts/flows/F/_schemas.py`
- tests for new contract paths and required columns

### Stage 2

Build the policy snapshot and prepared input view.

Files:
- `F070_build_backtest_policy_snapshot.py`
- `F071_build_backtest_input_view.py`

### Stage 3

Build the daily replay engine.

Files:
- `F072_run_backtest_replay.py`

### Stage 4

Build the one-row summary output.

Files:
- `F073_build_backtest_summary.py`

### Stage 5

Merge summary into O source view and show it in the operator UI.

Files:
- `O001_build_restock_source_view.py`
- `O400_operator_ui.py`

### Stage 6

Run the small calibration set and adjust once.

Calibration set:
- around 15 to 20 ASINs
- obvious good
- obvious bad
- Amazon-risk
- seasonal
- compression-risk
- sparse-data

## Tests And Health Requirements

Per repo rules, v1 must include:

- output contracts for every new file
- schema tests for every new file
- a scoped health/check item for the new backtest outputs
- idempotent builders

Minimum test coverage:

- contract path and schema test
- replay engine unit tests with fixed fixtures
- summary builder tests
- O source-view merge tests
- O UI display test for new backtest columns

### Exact first test files to create or update

Update:
- `tests/test_f000_paths_and_schemas.py`
  - add the 5 new F output contracts

Create:
- `tests/test_f070_build_backtest_policy_snapshot.py`
- `tests/test_f071_build_backtest_input_view.py`
- `tests/test_f072_run_backtest_replay.py`
- `tests/test_f073_build_backtest_summary.py`

Update:
- `tests/test_o001_restock_source_view.py`
  - add merge coverage for new backtest summary columns

Update:
- `tests/test_o_ui_operator_view.py`
  - add render coverage for the new backtest fields in the operator display

### Exact first fixture files to create

Create:
- `tests/fixtures/f_backtest/chart_daily_raw_sample.csv`
- `tests/fixtures/f_backtest/product_db_preview_sample.csv`
- `tests/fixtures/f_backtest/sku_sales_velocity_sample.csv`
- `tests/fixtures/f_backtest/sku_performance_summary_sample.csv`
- `tests/fixtures/f_backtest/listing_offer_snapshot_latest_sample.csv`

Scenario coverage for those fixtures:
- clean winner
- Amazon pressure
- seasonal slowdown
- stretched-price low-sales case
- multi-SKU ASIN mapping case
- sparse-history manual-review case

### Exact health-check expectations

Add a new F-scoped health file:
- `out/systems/F/live/feeder_backtest_health.csv`

Initial health checks to implement:

1. `f_backtest_policy_single_active_row`
- `FAIL` if active policy rows is not exactly `1`
- `OK` if exactly `1`

2. `f_backtest_input_view_schema`
- `FAIL` if file is missing or required columns are missing

3. `f_backtest_replay_daily_schema`
- `FAIL` if file is missing or required columns are missing when ready input rows exist

4. `f_backtest_summary_schema`
- `FAIL` if file is missing or required columns are missing when ready input rows exist

5. `f_backtest_summary_row_coverage`
- `FAIL` if any `input_status = ready` row lacks exactly one summary row on `seller_sku + asin + policy_id`

6. `f_backtest_replay_row_coverage`
- `FAIL` if any summary row has zero replay rows on `seller_sku + asin + policy_id`

7. `f_backtest_low_confidence_share`
- `WARN` if more than `50%` of summary rows are `history_confidence = low`

8. `f_backtest_manual_review_share`
- `WARN` if more than `40%` of summary rows end as `Manual review`

9. `f_backtest_join_resolution`
- `WARN` if any input rows have `mapping_status` of:
  - `multi_sku_asin_match`
  - `no_product_db_match`

Important v1 rule:
- these backtest health checks are F-scoped
- they must not block unrelated O restock recommendations from rendering
- O should degrade gracefully by leaving backtest columns blank when no summary row exists

## Recommended First Ticket Split

Do not build everything in one ticket.

Use this order:

1. contracts and policy snapshot
2. input view
3. replay engine
4. summary output
5. O integration
6. calibration adjustments

## Definition Of Done For V1 Planning

This coding plan is ready to implement when:

- new F outputs are agreed
- active policy storage path is agreed
- O integration columns are agreed
- provisional share assumptions are accepted as placeholders
- the small calibration set is selected
