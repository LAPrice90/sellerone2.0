# Data Contracts

## Dataset 1
- Name:
  - H strategy outcome log
- Owner script:
  - planned H repricer runtime path
  - primary writers expected in `scripts/phase1/phase1_main_loop.py`
  - optional publish shaping in `scripts/flows/H/H130_build_phase1_observation_sheet.py`
- Purpose:
  - create one decision-grade row per live tactic decision so we can judge whether the repricer logic is working
- Path:
  - `out/h_strategy_outcome_log.csv`
- Grain:
  - one row per `event_ts_utc + sku + tactic_case_id`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `event_ts_utc` | string | yes | when the tactic decision was recorded |
| `run_id` | string | yes | H run that produced the row |
| `sku` | string | yes | SellerOne SKU |
| `asin` | string | yes | Amazon ASIN |
| `scenario_type` | string | yes | market-shape classification such as `single_rival_reset`, `multi_seller_ladder_cap`, `share_hold`, `raise_find_loss`, `controlled_exit`, `suppression_reactivation` |
| `chosen_tactic` | string | yes | actual tactic selected by the engine |
| `buy_box_state_before` | string | yes | buy box state before the tactic decision |
| `buy_box_state_after` | string | planned Batch 003 | buy box state after the observation window closes |
| `seller_count` | integer | yes | number of distinct live sellers in the comparable ladder |
| `lowest_price_1_gbp` | decimal | yes | cheapest live comparable landed price |
| `lowest_price_2_gbp` | decimal | no | second-cheapest live comparable landed price when present |
| `lowest_price_3_gbp` | decimal | no | third-cheapest live comparable landed price when present |
| `our_price_before_gbp` | decimal | yes | our observed price before action |
| `target_price_gbp` | decimal | yes | target price chosen by the tactic |
| `price_written_gbp` | decimal | no | actual price submitted when a write occurs |
| `hold_until_utc` | string | no | when the current hold or observation window expires |
| `response_window_minutes` | integer | yes | how long the tactic expects to wait for outcome evidence |
| `retry_budget_remaining` | integer | yes | retries left for this tactic path |
| `stop_rule_code` | string | no | stop condition that ended further action |
| `writer_outcome` | string | yes | `APPLIED`, `NO_WRITE_REQUIRED`, `READ_ONLY_NO_WRITE`, `WRITE_REJECTED`, or similar |
| `tactic_success_state` | string | planned Batch 003 | `pending`, `success`, `failed`, `aborted`, `expired` |
| `reason_codes_json` | string | yes | reason-coded decision trail |
| `tactic_case_id` | string | yes | stable id for joining open and resolved rows |

### Freshness
- Loaded-at field:
  - `event_ts_utc`
- Warn if older than:
  - 1 H cycle
- Fail if older than:
  - 3 H cycles

### Quality checks
- Unique key:
  - `event_ts_utc + sku + tactic_case_id`
- Null rules:
  - `scenario_type`, `chosen_tactic`, `seller_count`, `our_price_before_gbp`, `target_price_gbp`, `response_window_minutes`, `retry_budget_remaining`, `writer_outcome`, and `reason_codes_json` must never be blank
- Accepted values:
  - `scenario_type` and `chosen_tactic` must come from fixed controlled sets
  - `seller_count >= 0`
  - `retry_budget_remaining >= 0`
  - `response_window_minutes >= 0`

### Downstream consumers
- operator review
- H strategy rollup
- H observation sheet / dashboard
- health checks for tactic completeness

### Failure effect
- We cannot tell whether the ladder-aware logic is working or just producing noise.

### Change rule
- Any new tactic or scenario type must update:
- this contract
- runtime tests
- health checks

## Dataset 2
- Name:
  - H strategy daily rollup
- Owner script:
  - planned daily rollup builder under H flow
- Purpose:
  - provide one operator-facing daily summary of tactic usage and success
- Path:
  - `out/h_strategy_outcome_daily.csv`
- Grain:
  - one row per `asof_date + scenario_type + chosen_tactic`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `asof_date` | string | yes | UTC date |
| `scenario_type` | string | yes | ladder scenario bucket |
| `chosen_tactic` | string | yes | tactic being summarized |
| `decision_rows` | integer | yes | count of tactic rows |
| `applied_rows` | integer | yes | count of applied writes |
| `no_write_rows` | integer | yes | count of no-write rows |
| `resolved_rows` | integer | planned Task 6 | count of rows in terminal states |
| `pending_rows` | integer | planned Task 6 | count of rows awaiting outcome close |
| `success_rows` | integer | planned Batch 003 | count of rows later judged successful |
| `failed_rows` | integer | planned Batch 003 | count of rows later judged failed |
| `expired_rows` | integer | planned Task 6 | count of rows that timed out without trusted outcome evidence |
| `aborted_rows` | integer | planned Task 6 | count of rows intentionally stopped without success/fail judgment |
| `avg_seller_count` | decimal | yes | average live seller count for the tactic |
| `avg_price_gap_to_lowest_gbp` | decimal | yes | average gap between our before-price and the cheapest rival |
| `below_break_even_rows` | integer | yes | count of rows at or below break-even |
| `at_floor_rows` | integer | yes | count of rows at or below active floor |
| `notes` | string | no | summary notes or alert reasons |

### Freshness
- Loaded-at field:
  - `asof_date`
- Warn if older than:
  - 24 hours
- Fail if older than:
  - 48 hours

### Quality checks
- Unique key:
  - `asof_date + scenario_type + chosen_tactic`
- Null rules:
  - all count and average fields must be explicit, including zero
- Accepted values:
  - counts must be non-negative integers
  - averages must be numeric when rows exist

### Downstream consumers
- daily operator review
- strategy alignment review
- H health / alert surface

### Failure effect
- The repricer can appear busy without any plain-language proof of whether tactic selection is sensible.

### Change rule
- Do not change the aggregation grain without updating downstream review docs and checks.

## Dataset 3
- Name:
  - H ceiling events
- Owner script:
  - planned H repricer runtime path
- Purpose:
  - record which ceiling actually constrained the decision and why
- Path:
  - `out/h_ceiling_events.csv`
- Grain:
  - one row per `event_ts_utc + sku + ceiling_event_id`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `event_ts_utc` | string | yes | event timestamp |
| `run_id` | string | yes | H run id |
| `sku` | string | yes | SellerOne SKU |
| `ceiling_event_id` | string | yes | stable event id |
| `compliance_ceiling_gbp` | decimal | no | compliance ceiling seen by runtime |
| `eligibility_ceiling_gbp` | decimal | no | eligibility ceiling seen by runtime |
| `demand_ceiling_gbp` | decimal | planned later | demand ceiling once live |
| `suppression_ceiling_gbp` | decimal | no | suppression temporary ceiling when active |
| `true_binding_ceiling_gbp` | decimal | yes | actual ceiling that constrained the action |
| `true_binding_ceiling_type` | string | yes | `COMPLIANCE`, `ELIGIBILITY`, `DEMAND`, `SUPPRESSION_TEMP`, or similar |
| `target_price_gbp` | decimal | yes | proposed target before write gate resolution |
| `hard_floor_gbp` | decimal | yes | hard floor active in the same decision |
| `ceiling_conflict_flag` | string | yes | `0` or `1` |
| `reason_codes_json` | string | yes | ceiling and clamp reasons |

### Freshness
- Loaded-at field:
  - `event_ts_utc`
- Warn if older than:
  - 1 H cycle
- Fail if older than:
  - 3 H cycles

### Quality checks
- Unique key:
  - `event_ts_utc + sku + ceiling_event_id`
- Null rules:
  - binding ceiling fields and reason codes must never be blank
- Accepted values:
  - `ceiling_conflict_flag` must be `0` or `1`
  - `true_binding_ceiling_type` must be from a fixed controlled set

### Downstream consumers
- operator review
- strategy outcome log joins
- health checks for missing ceiling truth

### Failure effect
- We cannot tell whether H is being limited by the right ceiling or by a broken clamp.

### Change rule
- If a new ceiling type is added, update both runtime truth and dashboard truth in the same batch.

## Dataset 4
- Name:
  - H suppression case log
- Owner script:
  - existing H suppression logging path, normalized in Batch 001
- Purpose:
  - preserve one case-level record for suppression entry, target selection, persistence, and resolution
- Path:
  - `out/h_suppression_cases.csv`
- Grain:
  - one row per `suppression_case_id`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `suppression_case_id` | string | yes | stable case id |
| `sku` | string | yes | SellerOne SKU |
| `asin` | string | yes | Amazon ASIN |
| `start_utc` | string | yes | when suppression was first recognized |
| `last_seen_utc` | string | yes | latest confirmation time |
| `buy_box_state` | string | yes | suppression state classification |
| `target_source` | string | yes | `CPT`, `COMPETITIVE_PRICE`, `AVERAGE_SELLING_PRICE`, `FOEP`, `PROBE_BRACKET`, `INFERRED_UPPER_BOUND`, `NONE` |
| `reactivation_target_landed_gbp` | decimal | no | direct target when one exists |
| `ceiling_landed_temp` | decimal | yes | active temporary suppression ceiling |
| `threshold_estimate_gbp` | decimal | no | learned threshold estimate when present |
| `threshold_confidence` | decimal | yes | confidence in the estimate |
| `anchor_floor_gbp` | decimal | yes | floor that suppression logic must not breach |
| `case_status` | string | yes | `active`, `resolved`, `aborted`, `expired` |
| `resolution_reason` | string | no | how the case ended |
| `reason_codes_json` | string | yes | reason-coded trail |

### Freshness
- Loaded-at field:
  - `last_seen_utc`
- Warn if older than:
  - 1 H cycle for active cases
- Fail if older than:
  - 3 H cycles for active cases

### Quality checks
- Unique key:
  - `suppression_case_id`
- Null rules:
  - `target_source`, `ceiling_landed_temp`, `threshold_confidence`, `anchor_floor_gbp`, `case_status`, and `reason_codes_json` must not be blank
- Accepted values:
  - `case_status` must be from a fixed controlled set
  - `target_source` must be explicit; use `NONE` rather than blank

### Downstream consumers
- suppression review
- strategy outcome joins
- health checks for blank suppression truth

### Failure effect
- Suppression can loop silently without any operator-grade explanation.

### Change rule
- Blank suppression target fields are not allowed once Batch 001 lands.
