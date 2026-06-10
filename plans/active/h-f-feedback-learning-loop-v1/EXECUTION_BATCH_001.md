# Execution Batch 001

## Name
- Joined evidence baseline

## Purpose
- Build the first joined read-only learning layer from data we already have.

## Prerequisite
- execution prep gate complete
- Batch 000 complete
- `FROZEN_INPUT_MANIFEST.md` remains unchanged from the prep gate
- `PHASE_SCORECARD.md` carries pass status for Prep and Phase 0

## Why this batch follows Batch 000
- It turns the locked identity and assumption foundation into usable joined evidence for learning.
- It keeps the work low-risk because it does not change live repricing or live buy decisions.

## Scope
- In scope:
  - one new one-off builder for joined evidence
  - targeted tests
  - output schema definition
  - row-reconciliation proof
  - scrape-owner reuse note and coverage-gap output
  - consume the Batch 000 identity bridge and frozen assumption snapshots
- Out of scope:
  - live H logic changes
  - F decision logic changes
  - loop promotion
  - Sheets or DB writes

## Planned files
- `scripts/one_off/HF001_build_learning_baseline.py`
- `tests/test_hf_learning_baseline.py`
- `plans/active/h-f-feedback-learning-loop-v1/*`

## Inputs
- `out/analysis_reports/hf_learning_identity_bridge_latest.csv`
- `out/analysis_reports/hf_learning_assumption_snapshots_latest.csv`
- `out/h_strategy_outcome_log.csv`
- `out/h_strategy_outcome_daily.csv`
- `out/listing_offer_snapshot_latest.csv`
- `out/listing_offer_seller_snapshot_latest.csv`
- `out/listing_offer_history.csv`
- `out/listing_offer_seller_observation_history.csv`
- `out/hos_daily_market_snapshot_latest.csv`
- `out/sku_performance_summary.csv`
- `out/sku_sales_velocity.csv`
- `out/analysis_reports/f_sales_history_validation_latest.csv`
- `out/analysis_reports/f_backtest_calibration_set_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv`

## Outputs
- `out/analysis_reports/hf_learning_market_facts_latest.csv`
- `out/analysis_reports/hf_learning_action_outcomes_latest.csv`
- `out/analysis_reports/hf_learning_scrape_gap_report_latest.csv`

## Proof required
- targeted tests pass
- outputs build with nonzero rows
- keys reconcile to source counts
- scrape coverage, stale coverage, and missing evidence rates are reported
- builder proves it is read-only against scanner-owned source files
- builder proves it is consuming the locked identity and assumption foundation instead of rebuilding joins ad hoc
- a short batch reply records:
  - row counts
  - join keys used
  - unresolved source gaps
  - current scrape owner path to use for fresh evidence

## Next step after success
- start Batch 002 and build the 30-day alignment pack plus explicit rescrape trigger rules
