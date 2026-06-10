# Data Contracts

## Dataset 1
- Name:
  - BBP raw monthly sales history evidence
- Owner script:
  - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- Purpose:
  - capture the raw BBP monthly chart in a form the rest of F can trust
- Path:
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- Grain:
  - one row per scraped listing observation

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `asin` | string | yes | listing identity |
| `seller_sku` | string | no | SKU when known |
| `bbp_sales_chart_month_labels` | string | yes | ordered month labels from BBP chart |
| `bbp_sales_chart_month_units` | string | yes | ordered month units from BBP chart |
| `bbp_sales_last_completed_month_label` | string | yes | trusted completed month label |
| `bbp_sales_last_completed_month_units` | string | yes | trusted completed month units |
| `bbp_sales_current_month_label` | string | yes | current partial month label when present |
| `bbp_sales_current_month_units` | string | yes | current partial month units when present |
| `bbp_sales_future_month_count_ignored` | string | yes | count of predicted future months ignored |

### Freshness
- Loaded-at field:
  - `observed_utc`
- Warn if older than:
  - after any scrape or demand-basis logic change
- Fail if older than:
  - when later decision outputs are rebuilt from a newer schema than this dataset

### Quality checks
- Unique key:
  - latest row per listing observation
- Null rules:
  - completed/current/future fields must be populated explicitly even when values are zero
- Accepted values:
  - predicted months are allowed in the raw capture but must be counted separately from trusted demand

### Downstream consumers
- `F071_build_backtest_input_view.py`
- sampled-ASIN audit and later validation audit

### Failure effect
- The whole sales history model loses its trust root.

### Change rule
- Do not hand-edit raw evidence.
- Rerun the scrape path instead.

## Dataset 2
- Name:
  - Sales history feature view
- Owner script:
  - `scripts/flows/F/F071_build_backtest_input_view.py`
- Purpose:
  - hold the listing-level features used to calculate demand, stability, confidence, and decision outputs
- Path:
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
- Grain:
  - one row per `seller_sku + asin + policy_id`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `seller_sku` | string | yes | SellerOne SKU |
| `asin` | string | yes | listing identity |
| `demand_basis_source` | string | yes | trusted raw demand source used for the row |
| `demand_basis_units_monthly` | string | yes | raw observed monthly units from trusted completed month rule |
| `bbp_sales_replay_demand_basis_source` | string | yes | explicit replay basis source |
| `bbp_sales_replay_demand_basis_units` | string | yes | explicit replay basis units |
| `history_confidence` | string | yes | current confidence level |
| `manual_review_flag` | string | yes | explicit hold flag |
| `history_maturity_state` | string | yes | no_history, recent_only, developing, stable, full_year |
| `price_qualified_units_monthly` | string | yes | expected monthly units available to us at our economics |
| `price_qualified_profit_monthly_gbp` | string | yes | expected monthly profit available to us at our economics |
| `price_qualification_reason_codes` | string | yes | why units were discounted or excluded |

### Freshness
- Loaded-at field:
  - `observed_utc`
- Warn if older than:
  - after any demand, pricing, or decision-rule change
- Fail if older than:
  - when summary or health is rebuilt from newer input logic

### Quality checks
- Unique key:
  - one row per `seller_sku + asin + policy_id`
- Null rules:
  - trusted demand source and units must be non-blank
  - maturity and price-qualified fields must be non-blank
- Accepted values:
  - raw observed demand and price-qualified demand must both be explicit when qualification is enabled
  - READY rows must use trusted demand basis (`bbp_last_completed_month` or `bbp_zero_history`)

### Downstream consumers
- `F072_run_backtest_replay.py`
- `F073_build_backtest_summary.py`
- validation audit

### Failure effect
- Pass/fail can be driven by the wrong type of demand.

### Change rule
- Any new feature column must be added with health and test coverage in the same batch.

## Dataset 3
- Name:
  - Sales history decision summary
- Owner script:
  - `scripts/flows/F/F073_build_backtest_summary.py`
- Purpose:
  - produce the business-facing output row per listing
- Path:
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
- Grain:
  - one row per `seller_sku + asin + policy_id`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `seller_sku` | string | yes | SellerOne SKU |
| `asin` | string | yes | listing identity |
| `summary_status` | string | yes | ready or manual-review style state |
| `recommendation` | string | yes | current richer fit label |
| `decision_state` | string | yes | `pass`, `fail`, or `manual_review` |
| `expected_units_next_30d` | string | yes | expected units if bought now |
| `expected_profit_next_30d_gbp` | string | yes | expected profit if bought now |
| `history_maturity_state` | string | planned Batch 003 | maturity state carried through |
| `seasonality_state` | string | planned Batch 003 | seasonal classification |
| `recent_performance_state` | string | planned Batch 003 | underperforming, stable, overperforming, or insufficient_history |
| `confidence` | string | planned Batch 004 | overall decision confidence |
| `decision_reason_codes` | string | yes | plain-language reason tags |

### Freshness
- Loaded-at field:
  - `observed_utc`
- Warn if older than:
  - after any input, replay, or decision-rule change
- Fail if older than:
  - when operator review is based on older summary than current input/replay

### Quality checks
- Unique key:
  - one row per `seller_sku + asin + policy_id`
- Null rules:
  - current required summary fields must remain present
  - new decision fields become required when their batch lands
- Accepted values:
  - `decision_state` must stay within `pass`, `fail`, `manual_review`

### Downstream consumers
- operator review
- later O surfaces if promoted

### Failure effect
- Operators see a result that sounds commercial but does not map to the written rules.

### Change rule
- Never change summary language without updating the decision model and tests together.

## Dataset 4
- Name:
  - Sales history validation audit
- Owner script:
  - `scripts/one_off/F005_build_sales_history_validation_audit.py`
- Purpose:
  - expose month-level evidence used by demand basis and decision outputs
- Path:
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- Grain:
  - one row per sampled `seller_sku + asin + month_index`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `seller_sku` | string | yes | sampled SKU |
| `asin` | string | yes | sampled ASIN |
| `amazon_link` | string | yes | direct product link |
| `month_class` | string | yes | completed_history, last_completed, current_partial, future_predicted |
| `trusted_for_demand_basis` | string | yes | `1` only for trusted completed-month basis row |
| `raw_observed_monthly_units` | string | yes | raw observed monthly demand basis |
| `price_qualified_monthly_units` | string | yes | qualified monthly units at our economics |
| `price_qualified_profit_monthly_gbp` | string | yes | qualified monthly profit at our economics |
| `decision_state` | string | yes | summary decision state joined for sampled review |
| `decision_confidence` | string | yes | summary decision confidence joined for sampled review |
| `decision_reason_codes` | string | yes | summary decision reason path |
| `summary_reason_codes` | string | yes | summary reason path for cross-check |

### Freshness
- Loaded-at field:
  - `observed_utc`
- Warn if older than:
  - after any demand, qualification, or decision-rule change
- Fail if older than:
  - when user sign-off relies on older validation logic

### Quality checks
- Unique key:
  - one row per sampled `seller_sku + asin + month_index`
- Null rules:
  - link, month class, trusted flag, and decision fields must be present
- Accepted values:
  - `month_class` must stay inside:
    - `completed_history`
    - `last_completed`
    - `current_partial`
    - `future_predicted`

### Downstream consumers
- operator review
- Batch 006 accuracy pack build

### Failure effect
- Operator review loses the month-level evidence trail behind decisions.

### Change rule
- Keep this one-off only.

## Dataset 5
- Name:
  - Sales history accuracy pack
- Owner script:
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- Purpose:
  - compare model outputs against sampled operator checks and expose explicit error buckets
- Paths:
  - `out/analysis_reports/f_sales_history_accuracy_pack_latest.csv`
  - `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
  - `out/analysis_reports/f_operator_sales_checks_template_latest.csv`
- Grain:
  - one row per sampled `seller_sku + asin`

### Required columns (accuracy pack)
| Column | Type | Required | Meaning |
|---|---|---|---|
| `seller_sku` | string | yes | sampled SKU |
| `asin` | string | yes | sampled ASIN |
| `model_decision_state` | string | yes | model decision from latest summary |
| `model_decision_confidence` | string | yes | model confidence from latest summary |
| `model_expected_units_next_30d` | string | yes | model expected units now |
| `operator_units_sold_30d_text` | string | yes | operator-entered sold-30d text |
| `operator_decision_state` | string | yes | operator decision for sampled listing |
| `units_alignment_state` | string | yes | aligned, moderate mismatch, severe mismatch, or missing data |
| `decision_alignment_state` | string | yes | aligned, mismatch, or missing data |
| `mismatch_flag` | string | yes | explicit mismatch marker |
| `accuracy_bucket_codes` | string | yes | explicit error buckets and missing-data buckets |

### Freshness
- Loaded-at field:
  - `observed_utc`
- Warn if older than:
  - after any summary decision-rule change
- Fail if older than:
  - when operator sign-off relies on stale comparison

### Quality checks
- Unique key:
  - one row per sampled `seller_sku + asin`
- Null rules:
  - model decision fields and bucket codes must be present
- Accepted values:
  - `mismatch_flag` must be `0` or `1`

### Downstream consumers
- operator validation workflow
- later tuning and calibration work

### Failure effect
- Decision quality can drift without a truthful model-vs-operator gap report.

### Change rule
- Keep this one-off only.

## Dataset 6
- Name:
  - Sales history learning log
- Owner script:
  - `scripts/one_off/F012_build_sales_history_learning_pack.py`
- Purpose:
  - record buy-time assumptions and compare them with the next 90 days of actual outcome
- Path:
  - `out/systems/F/live/feeder_sales_history_learning_live.csv`
- Grain:
  - one row per buy decision snapshot plus later review state

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `decision_snapshot_utc` | string | yes | when the buy assumption was recorded |
| `seller_sku` | string | yes | SellerOne SKU |
| `asin` | string | yes | listing identity |
| `expected_units_next_30d` | string | yes | forecast at buy time |
| `expected_profit_next_30d_gbp` | string | yes | profit forecast at buy time |
| `actual_units_30d` | string | yes | actual result after observation |
| `actual_profit_30d_gbp` | string | yes | actual realized profit |
| `actual_units_60d` | string | yes | cumulative units by 60-day checkpoint |
| `actual_profit_60d_gbp` | string | yes | cumulative profit by 60-day checkpoint |
| `actual_units_90d` | string | yes | cumulative units by 90-day checkpoint |
| `actual_profit_90d_gbp` | string | yes | cumulative profit by 90-day checkpoint |
| `learning_outcome` | string | yes | right_call, demand_too_high, demand_too_low, pending_outcome, and explicit operator overrides |
| `learning_reason_codes` | string | yes | why the assumption missed or held |

### Freshness
- Loaded-at field:
  - `decision_snapshot_utc`
- Warn if older than:
  - when learning review is due but snapshots do not exist
- Fail if older than:
  - when the system is being tuned without preserved buy-time assumptions

### Quality checks
- Unique key:
  - one row per decision snapshot
- Null rules:
  - snapshot identity and outcome fields required once the dataset is live
- Accepted values:
  - learning outcomes must use a fixed controlled set

### Downstream consumers
- later calibration work
- operator learning review

### Failure effect
- The model cannot improve honestly because it has no preserved expectation trail.

### Change rule
- Do not backfill or rewrite history manually to make the model look smarter than it was at the time.
