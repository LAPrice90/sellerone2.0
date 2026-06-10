# Data Contracts

## Dataset 1
- Name: Backtest policy live
- Owner script: `scripts/flows/F/F070_build_backtest_policy_snapshot.py` and `scripts/flows/F/F075_apply_backtest_policy_updates.py`
- Purpose: hold exactly one active v1 policy row used by the replay
- Path: `out/systems/F/live/feeder_backtest_policy_live.csv`
- Grain: one row per active policy

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observed_utc` | string | yes | when the active row was written |
| `policy_id` | string | yes | active policy identity |
| `policy_version` | string | yes | policy version text |
| `policy_status` | string | yes | expected active status |
| `minimum_expected_profit_gbp` | string | yes | editable control |
| `entry_target_roi_pct` | string | yes | editable control |
| `working_floor_roi_pct` | string | yes | editable control |
| `exit_floor_roi_pct` | string | yes | editable control |
| `emergency_floor_roi_pct` | string | yes | editable control |

### Freshness
- Loaded-at field: `observed_utc`
- Warn if older than: on-demand only
- Fail if older than: after a code or policy change without refresh

### Quality checks
- Unique key: exactly one active row
- Null rules: editable controls must all be non-blank numeric text
- Accepted values: ROI ladder ordering must remain `entry >= working >= exit >= emergency`

### Downstream consumers
- `F071_build_backtest_input_view.py`
- `O400_operator_ui.py`

### Failure effect
- Replay may run with the wrong policy or fail to build deterministically.

### Change rule
- UI writes staged events to inbox only.
- Direct live-file edits are not the operator path.

## Dataset 2
- Name: Backtest summary live
- Owner script: `scripts/flows/F/F073_build_backtest_summary.py`
- Purpose: one decision row per listing for O consumption
- Path: `out/systems/F/live/feeder_backtest_summary_live.csv`
- Grain: one row per `seller_sku + asin + policy_id`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `seller_sku` | string | yes | SellerOne SKU |
| `asin` | string | yes | listing identity |
| `policy_id` | string | yes | policy used for replay |
| `summary_status` | string | yes | ready or manual-review style state |
| `history_confidence` | string | yes | confidence label |
| `market_viability_score` | string | yes | main viability score |
| `exit_risk_score` | string | yes | main risk score |
| `recommendation` | string | yes | operator-facing outcome |

### Freshness
- Loaded-at field: `observed_utc`
- Warn if older than: after any backtest code or policy change
- Fail if older than: when O is using stale summary after a new policy refresh was expected

### Quality checks
- Unique key: one row per `seller_sku + asin + policy_id`
- Null rules: required backtest display fields must exist for ready rows
- Accepted values: summary status and recommendation must stay within the F contract

### Downstream consumers
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O400_operator_ui.py`

### Failure effect
- O can lose backtest context or show blank/incorrect decision support.

### Change rule
- Add columns only through F and O contract-aware updates with tests.

## Dataset 3
- Name: Backtest health
- Owner script: `scripts/flows/F/F074_build_backtest_health.py`
- Purpose: scoped F proof that the new outputs are structurally usable
- Path: `out/systems/F/live/feeder_backtest_health.csv`
- Grain: one row per named health check

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `observed_utc` | string | yes | when checks were built |
| `check` | string | yes | named check |
| `status` | string | yes | `ok`, `warn`, or `fail` |
| `value` | string | yes | numeric/text result |
| `notes` | string | no | readable proof detail |

### Freshness
- Loaded-at field: `observed_utc`
- Warn if older than: after any F backtest code change
- Fail if older than: when newer code or policy changes exist but this health file was not rebuilt

### Quality checks
- Unique key: one row per `check`
- Null rules: `check`, `status`, and `value` required on every row
- Accepted values: expected v1 checks are the 9 named backtest health checks

### Downstream consumers
- operator review
- future plan status snapshots

### Failure effect
- The backtest can look finished without structural proof.

### Change rule
- New checks should be added only when the contract and tests are updated together.

## Dataset 4
- Name: Sampled-ASIN BBP sales audit
- Owner script: `scripts/one_off/F004_build_bbp_sales_sample_audit.py`
- Purpose: one-row-per-sampled-ASIN audit list for chart extraction and replay demand-basis verification
- Path: `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
- Grain: one row per sampled `seller_sku + asin`

### Required columns
| Column | Type | Required | Meaning |
|---|---|---|---|
| `seller_sku` | string | yes | sampled SKU identity |
| `asin` | string | yes | sampled listing identity |
| `amazon_link` | string | yes | direct listing check link |
| `bbp_sales_chart_month_labels` | string | yes | raw monthly chart labels captured by scraper |
| `bbp_sales_chart_month_units` | string | yes | raw monthly chart units captured by scraper |
| `bbp_sales_last_completed_month_units` | string | yes | trusted completed-month units from scraper |
| `demand_basis_source` | string | yes | replay demand source selected in input view |
| `demand_basis_units_monthly` | string | yes | monthly units used as replay basis |
| `mismatch_flag` | string | yes | `1` when audit detects basis mismatch |
| `mismatch_reason_codes` | string | yes | explicit mismatch reason tags |

### Freshness
- Loaded-at field: `observed_utc`
- Warn if older than: after any demand-basis logic change or sample-pack refresh
- Fail if older than: when batch sign-off requires full sampled-ASIN verification but audit output is stale or missing

### Quality checks
- Unique key: one row per sampled `seller_sku + asin`
- Null rules: link, demand basis, and mismatch fields must be non-blank
- Accepted values: `mismatch_flag` must be `0` or `1`

### Downstream consumers
- operator sample review during Batch 008/009 validation
- backtest demand-basis sign-off evidence pack

### Failure effect
- operator cannot verify whether demand-basis issues are isolated or widespread across sampled listings.

### Change rule
- Keep this script one-off only; do not place it inside daily loops.
