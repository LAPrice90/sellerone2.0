# Data Contracts

## Dataset
- Name:
  - `hf_scope_expansion_candidates_latest.csv`
- Owner script:
  - planned `scripts/one_off/HF010_build_scope_expansion_candidates.py`
- Purpose:
  - make H/F overlap recovery explicit and route eligible rows into the current F capture path
- Path:
  - `out/analysis_reports/hf_scope_expansion_candidates_latest.csv`
- Grain:
  - one row per `candidate_id + supplier_id + supplier_sku`

## Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| candidate_id | string | yes | feeder candidate identity |
| supplier_id | string | yes | source supplier |
| supplier_sku | string | yes | supplier SKU |
| asin | string | no | ASIN when known |
| identity_status | string | yes | current bridge status |
| route_bucket | string | yes | explicit recovery or block reason |
| in_h_scope_flag | int | yes | `1` if already in H scope |
| recommended_capture_path | string | yes | current owner path to use |
| priority_rank | int | yes | execution order hint |
| current_alignment_class | string | no | latest alignment class when present |

## Freshness
- Loaded-at field:
  - `observed_utc`
- Warn if older than:
  - latest foundation or alignment output
- Fail if older than:
  - 7 days when used for execution

## Quality checks
- Unique key:
  - `candidate_id + supplier_id + supplier_sku`
- Null rules:
  - `candidate_id`, `supplier_id`, `supplier_sku`, `identity_status`, `route_bucket`, `recommended_capture_path`, and `priority_rank` must be non-null
- Accepted values:
  - `route_bucket` must be an explicit recovery or block reason, not blank

## Downstream consumers
- overlap recovery execution batch
- future review pack and experiment queue builders

## Failure effect
- What breaks if this goes stale, missing, or malformed?
  - Batch 001 cannot turn zero-overlap proof into a controlled recovery queue.

## Change rule
- How this dataset can change safely:
  - add columns only with matching tests and keep route-bucket meanings explicit

## Dataset
- Name:
  - `hf_strategy_scorecard_latest.csv`
- Owner script:
  - planned `scripts/one_off/HF011_build_strategy_scorecard.py`
- Purpose:
  - score each H tactic on maturity, write chain, and realised outcome quality
- Path:
  - `out/analysis_reports/hf_strategy_scorecard_latest.csv`
- Grain:
  - one row per `scenario_type`

## Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| scenario_type | string | yes | tactic family or scenario bucket |
| decision_rows | int | yes | total decisions in scope |
| sample_min_rows | int | yes | maturity threshold |
| sample_mature_flag | int | yes | tactic is mature enough for evaluation |
| write_applied_rate | float | yes | applied writes / decision rows |
| failed_rate | float | yes | failed / decision rows |
| expired_rate | float | yes | expired / decision rows |
| actual_units_30d | float | no | realised units where linked |
| actual_profit_30d_gbp | float | no | realised profit where linked |
| review_status | string | yes | keep_observing / overlap_first / eligible_shadow / blocked |

## Freshness
- Loaded-at field:
  - `snapshot_utc`
- Warn if older than:
  - 1 day
- Fail if older than:
  - 7 days or older than current H strategy outputs used by downstream review

## Quality checks
- Unique key:
  - `scenario_type`
- Null rules:
  - `scenario_type`, `decision_rows`, `sample_min_rows`, `sample_mature_flag`, and `review_status` must be non-null
- Accepted values:
  - `sample_mature_flag` in `0,1`
  - `review_status` must be explicit and non-blank

## Downstream consumers
- review pack builder
- shadow experiment queue builder

## Failure effect
- What breaks if this goes stale, missing, or malformed?
  - thin-sample tactics can be misread as mature and wrongly promoted

## Change rule
- How this dataset can change safely:
  - keep one row per tactic and add tests whenever score columns or gates change

## Dataset
- Name:
  - `hf_strategy_experiment_queue_latest.csv`
- Owner script:
  - planned `scripts/one_off/HF013_build_strategy_experiment_queue.py`
- Purpose:
  - produce the shadow-only queue for future H strategy experiments
- Path:
  - `out/analysis_reports/hf_strategy_experiment_queue_latest.csv`
- Grain:
  - one row per proposed experiment cohort or tactic action

## Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| experiment_id | string | yes | queue identity |
| scenario_type | string | yes | tactic under review |
| shadow_only_flag | int | yes | must be `1` until a later live ticket proves otherwise |
| risk_gate_status | string | yes | pass / fail / review |
| sample_mature_flag | int | yes | copied from scorecard |
| max_cohort_size | int | yes | upper bound for any later runtime cohort |
| required_review_reason | string | yes | why this row is or is not eligible |

## Freshness
- Loaded-at field:
  - `snapshot_utc`
- Warn if older than:
  - latest scorecard rebuild
- Fail if older than:
  - any downstream consumer that is newer than this queue

## Quality checks
- Unique key:
  - `experiment_id`
- Null rules:
  - all required columns non-null
- Accepted values:
  - `shadow_only_flag` must be `1`
  - `risk_gate_status` must be explicit

## Downstream consumers
- optional F shadow calibration handoff
- later H runtime cohort ticket

## Failure effect
- What breaks if this goes stale, missing, or malformed?
  - future experiments lose their guardrails and review reasons

## Change rule
- How this dataset can change safely:
  - preserve shadow-only semantics until a later live ticket changes scope with proof
