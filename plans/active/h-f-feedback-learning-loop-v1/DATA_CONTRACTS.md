# Data Contracts

## Dataset 1
- Name: `HF learning market facts`
- Owner script: `scripts/one_off/HF001_build_learning_baseline.py`
- Purpose: one joined market-state row per SKU observation so H and F can reason from the same facts
- Path: `out/analysis_reports/hf_learning_market_facts_latest.csv`
- Grain: one row per `observation_utc + sku + asin`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observation_utc` | datetime UTC | yes | observation timestamp |
| `asof_date` | date | yes | observation date |
| `sku` | string | yes | SKU key |
| `asin` | string | yes | ASIN key |
| `our_price_gbp` | decimal | no | our observed live price |
| `buy_box_price_gbp` | decimal | no | observed buy box price |
| `lowest_fba_price_gbp` | decimal | no | observed lowest FBA |
| `lowest_fbm_price_gbp` | decimal | no | observed lowest FBM |
| `offer_count_fba` | integer | no | FBA competition count |
| `offer_count_fbm` | integer | no | FBM competition count |
| `amazon_present_flag` | `0/1` | yes | whether Amazon was present |
| `seller_entry_count_today` | integer | no | seller entries from market snapshot |
| `seller_exit_count_today` | integer | no | seller exits from market snapshot |
| `delivery_parity_flag` | `0/1` | yes | our delivery parity view |
| `break_even_gross_gbp` | decimal | no | economics anchor |
| `bsr` | decimal | no | listing rank context when available |

### Quality checks
- Unique key:
  - `observation_utc + sku + asin`
- Null rules:
  - `observation_utc`, `asof_date`, `sku`, `asin`, `amazon_present_flag`, `delivery_parity_flag` must be non-blank
- Accepted values:
  - binary flags in `{0,1}`
  - price/count fields must parse if populated

### Planned health checks
- `hf_learning_market_facts_schema`
- `hf_learning_market_facts_key_integrity`
- `hf_learning_market_facts_source_coverage`

## Dataset 2
- Name: `HF learning action outcomes`
- Owner script: `scripts/one_off/HF001_build_learning_baseline.py`
- Purpose: record what H decided, what was written, and what happened after the response window
- Path: `out/analysis_reports/hf_learning_action_outcomes_latest.csv`
- Grain: one row per H tactic case or event

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `event_ts_utc` | datetime UTC | yes | decision timestamp |
| `run_id` | string | yes | H run identifier |
| `sku` | string | yes | SKU key |
| `asin` | string | yes | ASIN key |
| `scenario_type` | string | yes | H scenario bucket |
| `chosen_tactic` | string | yes | tactic chosen |
| `eligible_to_write_flag` | `0/1` | yes | whether the row was write-eligible |
| `decision_to_change_price_flag` | `0/1` | yes | whether H chose a price change |
| `write_attempted_flag` | `0/1` | yes | whether a write was attempted |
| `write_applied_flag` | `0/1` | yes | whether the write applied successfully |
| `our_price_before_gbp` | decimal | no | old price |
| `target_price_gbp` | decimal | no | target price |
| `price_written_gbp` | decimal | no | applied price |
| `buy_box_state_before` | string | no | before state |
| `buy_box_state_after` | string | no | after state |
| `seller_count` | integer | no | seller count used in decision |
| `response_window_minutes` | integer | no | wait window |
| `tactic_success_state` | string | yes | terminal state |
| `reason_codes_json` | json array or text | yes | reason tags |

### Quality checks
- Unique key:
  - `run_id + sku + event_ts_utc + chosen_tactic`
- Null rules:
  - all binary flags and key fields must be non-blank
- Accepted values:
  - binary flags in `{0,1}`
  - `write_applied_flag` must not be `1` when `write_attempted_flag` is `0`
  - `decision_to_change_price_flag` must not be `1` when `eligible_to_write_flag` is `0`

### Planned health checks
- `hf_learning_action_outcomes_schema`
- `hf_learning_action_outcomes_state_integrity`
- `hf_learning_action_outcomes_terminal_coverage`

## Dataset 3
- Name: `HF learning alignment 30d`
- Owner script: `scripts/one_off/HF002_build_learning_alignment.py`
- Purpose: compare expected demand/profit with actual results and the live market conditions around them
- Path: `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
- Grain: one row per `sku + asin + alignment_window_end`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `alignment_window_end_utc` | datetime UTC | yes | end of the measurement window |
| `sku` | string | yes | SKU key |
| `asin` | string | yes | ASIN key |
| `expected_units_30d` | decimal | no | F expected units |
| `expected_units_source` | string | no | source key used for expected units (`assumption_candidate_sku_asin`, `sales_validation_asin`, `full_capture_asin`, or `no_source`) |
| `expected_profit_30d_gbp` | decimal | no | F expected profit |
| `expected_profit_source` | string | no | source key used for expected profit (`assumption_candidate_sku_asin`, `calibration_asin`, `full_capture_asin`, or `no_source`) |
| `actual_units_30d` | decimal | no | actual units sold |
| `actual_profit_30d_gbp` | decimal | no | actual profit |
| `units_error_pct` | decimal | no | actual vs expected units delta |
| `profit_error_pct` | decimal | no | actual vs expected profit delta |
| `avg_seller_count` | decimal | no | average competition level in window |
| `amazon_presence_share_pct` | decimal | no | Amazon presence share |
| `avg_undercut_gap_gbp` | decimal | no | average undercut or ladder gap |
| `dominant_discrepancy_class` | string | yes | main explanation bucket |

### Quality checks
- Unique key:
  - `alignment_window_end_utc + sku + asin`
- Null rules:
  - `alignment_window_end_utc`, `sku`, `asin`, `dominant_discrepancy_class` must be non-blank

### Planned health checks
- `hf_learning_alignment_schema`
- `hf_learning_alignment_coverage`
- `hf_learning_alignment_freshness`

## Dataset 9
- Name: `HF learning factor impacts`
- Owner script: `scripts/one_off/HF002_build_learning_alignment.py`
- Purpose: summarize discrepancy buckets and carry explicit rescrape trigger decisions into one factor table
- Path: `out/analysis_reports/hf_learning_factor_impacts_latest.csv`
- Grain: one row per discrepancy factor bucket

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `snapshot_utc` | datetime UTC | yes | build timestamp |
| `factor_bucket` | string | yes | discrepancy or factor bucket |
| `sample_rows` | integer-like string | yes | supporting sample size |
| `avg_units_error_pct` | decimal-like string | no | average unit error bias for bucket |
| `avg_profit_error_pct` | decimal-like string | no | average profit error bias for bucket |
| `avg_seller_count` | decimal-like string | no | average seller count for bucket |
| `amazon_presence_share_pct` | decimal-like string | no | average Amazon presence share |
| `rescrape_trigger_flag` | `0/1` | yes | whether rescrape thresholds are breached |
| `rescrape_trigger_reason` | string | yes | explicit threshold reason codes |
| `rescrape_owner_path` | string | no | current owner path for refresh |
| `recommended_collection_mode` | string | yes | expected mode for collection routing |
| `thin_sample_flag` | `0/1` | yes | whether sample rows are below confidence floor |

### Quality checks
- Unique key:
  - `snapshot_utc + factor_bucket`
- Null rules:
  - `snapshot_utc`, `factor_bucket`, `sample_rows`, `rescrape_trigger_flag`, `rescrape_trigger_reason`, `recommended_collection_mode` must be non-blank

### Planned health checks
- `hf_learning_factor_impacts_schema`
- `hf_learning_factor_impacts_sample_guard`
- `hf_learning_factor_impacts_rescrape_trigger_consistency`

## Dataset 10
- Name: `HF learning health checklist`
- Owner script: `scripts/one_off/HF003_build_learning_health_checks.py`
- Purpose: one checklist for schema, row guards, freshness, and rescrape-trigger integrity across the learning outputs
- Path: `out/analysis_reports/hf_learning_health_checklist_latest.csv`
- Grain: one row per check

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observed_utc` | datetime UTC | yes | check timestamp |
| `check` | string | yes | check key |
| `status` | string | yes | `ok|warn|fail` |
| `value` | string | no | numeric or text value |
| `notes` | string | no | context details |

### Quality checks
- Unique key:
  - `observed_utc + check`
- Null rules:
  - `observed_utc`, `check`, `status` must be non-blank

### Planned health checks
- `hf_learning_health_checklist_schema`
- `hf_learning_health_checklist_status_mix`

## Dataset 11
- Name: `HF learning operator report`
- Owner script: `scripts/one_off/HF005_build_learning_operator_report.py`
- Purpose: provide one operator-facing rollup for H action behavior, scrape coverage, alignment drift, trigger state, and health status
- Path: `out/reports/hf_learning_operator_report_latest.csv`
- Grain: one row per report metric key

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observed_utc` | datetime UTC | yes | report timestamp |
| `section` | string | yes | metric section (`h_action`, `scrape_coverage`, `alignment`, `factor`, `health`) |
| `metric_key` | string | yes | metric identifier |
| `metric_value` | string | yes | metric value |
| `metric_text` | string | yes | plain-language metric meaning |
| `source_path` | string | yes | source file used for metric |

### Quality checks
- Unique key:
  - `observed_utc + section + metric_key`
- Null rules:
  - all required columns must be non-blank

### Planned health checks
- `hf_learning_operator_report_schema`
- `hf_learning_operator_report_metric_coverage`

## Dataset 4
- Name: `F feedback calibration`
- Owner script: `scripts/flows/F/F080_build_feedback_calibration_shadow.py`
- Purpose: shadow-mode factor weights or adjustments that F can read without changing live approval decisions
- Path: `out/systems/F/live/feeder_feedback_calibration_live.csv`
- Grain: one row per factor bucket or factor combination

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observed_utc` | datetime UTC | yes | build timestamp |
| `factor_bucket` | string | yes | bucket label |
| `sample_rows` | integer-like string | yes | supporting sample size from factor table |
| `avg_units_error_pct` | decimal-like string | no | average units error for the factor bucket |
| `avg_profit_error_pct` | decimal-like string | no | average profit error for the factor bucket |
| `avg_seller_count` | decimal-like string | no | average seller count context |
| `amazon_presence_share_pct` | decimal-like string | no | Amazon presence share context |
| `rescrape_trigger_flag` | `0/1` | yes | whether factor conditions request a rescrape |
| `rescrape_trigger_reason` | string | yes | reason code for trigger decision |
| `rescrape_owner_path` | string | no | owner path for rescrape routing |
| `recommended_collection_mode` | string | yes | expected `F061` collection mode |
| `alignment_class_rows` | integer-like string | yes | alignment rows contributing to this bucket |
| `queue_rows_current` | integer-like string | yes | queue snapshot row count at build time |
| `decision_rows_current` | integer-like string | yes | decision snapshot row count at build time |
| `queue_snapshot_hash` | sha256 hex | yes | hash of queue source used for guard |
| `decision_snapshot_hash` | sha256 hex | yes | hash of decision source used for guard |
| `source_alignment_path` | string | yes | alignment source file path used for build |
| `source_factor_path` | string | yes | factor source file path used for build |
| `shadow_only_flag` | `0/1` | yes | must stay shadow-only until approved |
| `apply_to_live_decisions_flag` | `0/1` | yes | must remain `0` until explicit promotion |
| `calibration_status` | string | yes | shadow readiness state for this row |

### Quality checks
- Unique key:
  - `observed_utc + factor_bucket`
- Null rules:
  - `observed_utc`, `factor_bucket`, `sample_rows`, `rescrape_trigger_flag`, `rescrape_trigger_reason`, `recommended_collection_mode`, `alignment_class_rows`, `queue_rows_current`, `decision_rows_current`, `queue_snapshot_hash`, `decision_snapshot_hash`, `source_alignment_path`, `source_factor_path`, `shadow_only_flag`, `apply_to_live_decisions_flag`, `calibration_status` must be non-blank
- Accepted values:
  - `shadow_only_flag` must be `1`
  - `apply_to_live_decisions_flag` must be `0`

### Planned health checks
- `f_feedback_calibration_schema`
- `f_feedback_calibration_sample_quality`
- `f_feedback_calibration_shadow_only_guard`

## Dataset 5
- Name: `HF learning scrape gap report`
- Owner script: `scripts/one_off/HF001_build_learning_baseline.py`
- Purpose: explain whether fresh scrape is needed and route that decision through current F owner tools
- Path: `out/analysis_reports/hf_learning_scrape_gap_report_latest.csv`
- Grain: one row per candidate or SKU needing review

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observed_utc` | datetime UTC | yes | build timestamp |
| `candidate_id` | string | no | F candidate key when available |
| `supplier_id` | string | no | supplier scope |
| `supplier_sku` | string | no | supplier SKU |
| `sku` | string | no | SKU key when available |
| `asin` | string | yes | ASIN key |
| `scrape_coverage_status` | string | yes | `ok|missing|stale|thin` style status |
| `rescrape_needed_flag` | `0/1` | yes | whether fresh scrape is recommended |
| `rescrape_reason_codes` | string | yes | why fresh scrape is needed |
| `queue_owner_path` | string | yes | current tool or owner path to use |

### Quality checks
- Unique key:
  - `candidate_id + asin` when candidate exists, else `supplier_sku + asin`
- Null rules:
  - `observed_utc`, `asin`, `scrape_coverage_status`, `rescrape_needed_flag`, `rescrape_reason_codes`, `queue_owner_path` must be non-blank

### Planned health checks
- `hf_learning_scrape_gap_schema`
- `hf_learning_scrape_gap_reason_coverage`
- `hf_learning_scrape_gap_queue_owner_truth`

## Dataset 6
- Name: `HF learning identity bridge`
- Owner script: `scripts/one_off/HF000_build_learning_foundation.py`
- Purpose: provide one explicit identity bridge so H, F, and E/B evidence are joined on declared keys instead of guessed joins
- Path: `out/analysis_reports/hf_learning_identity_bridge_latest.csv`
- Grain: one row per candidate in the frozen F lineage set

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `snapshot_utc` | datetime UTC | yes | build timestamp |
| `candidate_id` | string | yes | F candidate key |
| `feeder_candidate_id` | string | no | feeder candidate key when present |
| `supplier_id` | string | no | supplier scope |
| `supplier_sku` | string | no | supplier SKU |
| `asin` | string | no | ASIN key when present |
| `sku` | string | no | live or sold SKU key when resolvable |
| `sku_resolution_status` | string | yes | `RESOLVED_FROM_H_SNAPSHOT` or explicit unresolved code |
| `sku_resolution_source` | string | yes | source route used for resolution |
| `asin_value_count` | integer-like string | yes | number of distinct ASIN values seen for candidate |
| `supplier_sku_value_count` | integer-like string | yes | number of distinct supplier SKU values seen |
| `asin_conflict_flag` | `0/1` | yes | ASIN ambiguity flag |
| `supplier_sku_conflict_flag` | `0/1` | yes | supplier SKU ambiguity flag |
| `source_screening_flag` | `0/1` | yes | candidate observed in screening source |
| `source_recommendation_flag` | `0/1` | yes | candidate observed in recommendation source |
| `source_queue_flag` | `0/1` | yes | candidate observed in approval queue source |
| `source_decision_flag` | `0/1` | yes | candidate observed in approval decision source |
| `source_handoff_flag` | `0/1` | yes | candidate observed in PO handoff source |
| `source_event_count` | integer-like string | yes | lineage event row count for this candidate |
| `latest_source_utc` | datetime UTC | no | latest lineage timestamp captured |
| `latest_source_name` | string | no | lineage source name for latest event |

### Quality checks
- Unique key:
  - `candidate_id`
- Null rules:
  - `snapshot_utc`, `candidate_id`, `sku_resolution_status`, `sku_resolution_source` must be non-blank

### Planned health checks
- `hf_learning_identity_bridge_schema`
- `hf_learning_identity_bridge_coverage`
- `hf_learning_identity_bridge_ambiguity`

## Dataset 7
- Name: `HF learning assumption snapshots`
- Owner script: `scripts/one_off/HF000_build_learning_foundation.py`
- Purpose: freeze what F believed at approval or handoff time so later alignment compares actuals with the right historical assumptions
- Path: `out/analysis_reports/hf_learning_assumption_snapshots_latest.csv`
- Grain: one latest snapshot row per candidate from queue, decision, handoff, or recommendation lineage

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `snapshot_utc` | datetime UTC | yes | build timestamp |
| `candidate_id` | string | yes | F candidate key |
| `feeder_candidate_id` | string | no | feeder candidate key when present |
| `supplier_id` | string | no | supplier scope |
| `supplier_sku` | string | no | supplier SKU |
| `asin` | string | no | ASIN key when present |
| `snapshot_stage` | string | yes | `po_handoff|approval_decision|approval_queue|recommendation_only` |
| `assumption_anchor_utc` | datetime UTC | no | timestamp for selected snapshot stage |
| `assumption_anchor_source` | string | yes | source chosen for snapshot anchor |
| `in_scope_approval_decision_flag` | `0/1` | yes | whether candidate has approval decision lineage |
| `recommendation_status` | string | no | F recommendation at snapshot time |
| `decision_action` | string | no | human or routing action |
| `recommended_test_qty` | integer | no | quantity suggestion at snapshot time |
| `estimated_roi_pct` | decimal-like string | no | frozen ROI estimate |
| `estimated_margin_gbp` | decimal-like string | no | frozen margin estimate |
| `estimated_demand` | decimal-like string | no | frozen demand estimate |
| `final_decision_status` | string | no | final decision status when available |
| `decision_source` | string | no | decision source when available |
| `actor` | string | no | decision actor when available |
| `decision_utc` | datetime UTC | no | decision timestamp when available |
| `handoff_utc` | datetime UTC | no | handoff timestamp when available |
| `source_row_hash` | string | no | lineage source row hash |
| `source_file_path` | string | no | lineage source file path |
| `source_seen_at_utc` | datetime UTC | no | lineage source seen timestamp |

### Quality checks
- Unique key:
  - `candidate_id`
- Null rules:
  - `snapshot_utc`, `candidate_id`, `snapshot_stage`, `assumption_anchor_source`, `in_scope_approval_decision_flag` must be non-blank

### Planned health checks
- `hf_learning_assumption_snapshot_schema`
- `hf_learning_assumption_snapshot_coverage`
- `hf_learning_assumption_snapshot_stage_truth`

## Dataset 8
- Name: `HF learning foundation metrics`
- Owner script: `scripts/one_off/HF000_build_learning_foundation.py`
- Purpose: emit deterministic coverage metrics for Batch 000 proof and downstream phase scoring
- Path: `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
- Grain: one row per metric for each foundation snapshot

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `snapshot_utc` | datetime UTC | yes | build timestamp |
| `metric_name` | string | yes | metric identifier |
| `metric_value` | string | yes | metric value rendered as string |

### Quality checks
- Unique key:
  - `snapshot_utc + metric_name`
- Null rules:
  - `snapshot_utc`, `metric_name`, `metric_value` must be non-blank

### Planned health checks
- `hf_learning_foundation_metrics_schema`
- `hf_learning_foundation_metrics_expected_set`
