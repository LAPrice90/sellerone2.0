# Execution Batch 000

## Name
- Foundation lock

## Purpose
- Build the minimum truth layer needed so later learning compares the right item, the right time, and the right expectation.

## Prerequisite
- execution prep gate complete
- `FROZEN_INPUT_MANIFEST.md` locked
- `PHASE_SCORECARD.md` opened

## Why this batch is first
- Without an explicit identity bridge, later joined marts can silently compare the wrong records.
- Without frozen assumption snapshots, alignment can compare actuals against rewritten estimates instead of buy-time belief.
- Without fixed outcome windows, tactic reporting can drift and give different answers for the same action.

## Scope
- In scope:
  - one new one-off builder for identity and assumption truth
  - targeted tests
  - output schema definition
  - join-coverage proof
  - fixed measurement-window declaration
- Out of scope:
  - live H logic changes
  - live F recommendation changes
  - loop promotion
  - scrape execution

## Planned files
- `scripts/one_off/HF000_build_learning_foundation.py`
- `tests/test_hf_learning_foundation.py`
- `plans/active/h-f-feedback-learning-loop-v1/*`

## Inputs
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/systems/F/live/feeder_approval_queue_live.csv`
- `out/systems/F/history/feeder_approval_decisions_log.csv`
- `out/systems/F/live/feeder_po_handoff_ready_live.csv`
- `out/systems/F/live/feeder_candidate_recommendations_live.csv`
- `out/listing_offer_snapshot_latest.csv`
- `out/sku_performance_summary.csv`

## Outputs
- `out/analysis_reports/hf_learning_identity_bridge_latest.csv`
- `out/analysis_reports/hf_learning_assumption_snapshots_latest.csv`
- `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`

## Proof required
- targeted tests pass
- outputs build with nonzero rows where source evidence exists
- bridge coverage is reported explicitly
- unresolved bridge rows remain visible
- assumption snapshot stage coverage is reported explicitly
- measurement windows declared:
  - H: `15m`, `2h`, `24h`, `72h`
  - F: `30d`, `60d`, `90d`

## Next step after success
- start Batch 001 and build the joined read-only evidence marts on top of the locked foundation layer
