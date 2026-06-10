# Data Contracts

## Dataset 1
- Name: `H ceiling events`
- Owner script: `scripts/phase1/phase1_main_loop.py` via `scripts/phase1/phase1_storage.py`
- Purpose: preserve ceiling-source evidence and the effective binding ceiling used by runtime logic
- Path: `out/h_ceiling_events.csv`
- Grain: one ceiling-event row per SKU decision event

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `event_ts_utc` | datetime UTC | yes | event timestamp |
| `run_id` | string | yes | H run identifier |
| `sku` | string | yes | SKU key |
| `ceiling_event_id` | string | yes | event key |
| `compliance_ceiling_gbp` | decimal | no | raw compliance ceiling |
| `eligibility_ceiling_gbp` | decimal | no | raw eligibility ceiling |
| `demand_ceiling_gbp` | decimal | no | raw demand ceiling |
| `suppression_ceiling_gbp` | decimal | no | raw suppression ceiling |
| `true_binding_ceiling_gbp` | decimal | no | effective ceiling allowed to drive runtime logic |
| `true_binding_ceiling_type` | string | no | effective ceiling source |
| `target_price_gbp` | decimal | no | chosen target price |
| `hard_floor_gbp` | decimal | yes | absolute floor |
| `ceiling_conflict_flag` | `0/1` | yes | raw ceiling conflict visible for operator review |
| `reason_codes_json` | json array | yes | reason codes |

### Freshness
- Loaded-at field: `event_ts_utc`
- Warn if older than: `1 H cycle`
- Fail if older than: `3 H cycles`

### Quality checks
- Unique key: `ceiling_event_id`
- Null rules:
  - `event_ts_utc`, `run_id`, `sku`, `ceiling_event_id`, `hard_floor_gbp`, `ceiling_conflict_flag`, `reason_codes_json` must be non-blank
- Accepted values:
  - `ceiling_conflict_flag` in `{0,1}`
  - effective contract rule: if `true_binding_ceiling_gbp` is non-blank, it must be `>= hard_floor_gbp`
  - `reason_codes_json` must parse as a JSON array

### Downstream consumers
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/system_health_checklist.csv`
- operator review and plan evidence

### Failure effect
- What breaks if this goes stale, missing, or malformed?
  - operator cannot tell whether ceiling logic is safe
  - H can appear safe while still carrying invalid ceiling state

### Change rule
- How this dataset can change safely:
  - preserve raw source evidence
  - never hide a raw conflict by overwriting reason codes
  - if new raw/effective columns are added, keep existing consumers working and document the effective contract

## Dataset 2
- Name: `Phase 1 runtime floor snapshot latest`
- Owner script: `scripts/phase1/phase1_main_loop.py`
- Purpose: latest cross-section of H execution truth, floor truth, and suppression state
- Path: `out/phase1_runtime_floor_snapshot_latest.csv`
- Grain: latest snapshot row per SKU

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `snapshot_utc` | datetime UTC | yes | snapshot timestamp |
| `sku` | string | yes | SKU key |
| `execution_state` | string | no | current strategy state |
| `execution_write_status` | string | no | write result |
| `execution_hard_floor_gbp` | decimal | no | runtime hard floor |
| `true_binding_ceiling_gbp` | decimal | no | effective ceiling in snapshot |
| `trace_floor_total_gbp` | decimal | no | traced floor truth |
| `truth_status` | string | no | truth state marker |
| `floor_reconcile_delta_gbp` | decimal | no | floor reconciliation delta |

### Freshness
- Loaded-at field: `snapshot_utc`
- Warn if older than: existing H cadence
- Fail if older than: existing H cadence fail threshold

### Quality checks
- Unique key: `sku`
- Null rules:
  - `snapshot_utc` and `sku` must be non-blank
- Accepted values:
  - if `true_binding_ceiling_gbp` and `trace_floor_total_gbp` are both present, `true_binding_ceiling_gbp >= trace_floor_total_gbp`
  - if `execution_hard_floor_gbp` and `trace_floor_total_gbp` are both present, reconciliation must stay consistent with current floor contract

### Downstream consumers
- operator reviews
- plan validation
- future H output health checks

### Failure effect
- What breaks if this goes stale, missing, or malformed?
  - we lose the fastest truth view for live SKU-level repricer behavior

### Change rule
- How this dataset can change safely:
  - keep SKU-level snapshot semantics
  - any new columns must be additive and documented

## Dataset 3
- Name: `H strategy outcome daily`
- Owner script: `scripts/phase1/phase1_main_loop.py` via `scripts/phase1/phase1_storage.py`
- Purpose: daily operator rollup by scenario and tactic
- Path: `out/h_strategy_outcome_daily.csv`
- Grain: one row per `asof_date + scenario_type + chosen_tactic`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `asof_date` | date | yes | rollup date |
| `scenario_type` | string | yes | scenario bucket |
| `chosen_tactic` | string | yes | tactic bucket |
| `decision_rows` | integer | yes | decision count |
| `applied_rows` | integer | yes | applied write count |
| `no_write_rows` | integer | yes | non-applied count |
| `resolved_rows` | integer | yes | resolved count |
| `pending_rows` | integer | yes | pending count |
| `success_rows` | integer | yes | success count |
| `failed_rows` | integer | yes | failed count |
| `expired_rows` | integer | yes | timeout/no-proof terminal count |
| `aborted_rows` | integer | yes | constraint/stop terminal count |
| `below_break_even_rows` | integer | yes | count of rows landing at or below break-even contract |
| `at_floor_rows` | integer | yes | count of rows landing at the floor contract |

### Freshness
- Loaded-at field: `asof_date`
- Warn if older than: `24h`
- Fail if older than: `48h`

### Quality checks
- Unique key: `asof_date + scenario_type + chosen_tactic`
- Null rules:
  - all count columns must be non-blank integers
- Accepted values:
  - `applied_rows + no_write_rows = decision_rows`
  - `success_rows + failed_rows + expired_rows + aborted_rows <= decision_rows`
  - `at_floor_rows <= decision_rows`
  - `below_break_even_rows <= decision_rows`

### Downstream consumers
- `scripts/flows/A/A015_build_system_health_check.py`
- operator reviews
- plan sign-off scoring

### Failure effect
- What breaks if this goes stale, missing, or malformed?
  - operator cannot judge whether tactics are working
  - health checks can show false confidence or false noise

### Change rule
- How this dataset can change safely:
  - do not alter count meaning without updating A015 and plan docs
  - if metric semantics change, document the denominator explicitly
