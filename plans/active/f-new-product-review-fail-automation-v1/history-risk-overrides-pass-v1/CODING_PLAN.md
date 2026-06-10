# Coding Plan

## Ticket
- Name: `f-history-risk-overrides-pass-v1`
- Scope: history-risk audit and later clean Pass routing
- Owner flow: F

## Goal
- Build a read-only audit first.
- Count where clean Pass conflicts with history-risk evidence.
- Decide hard routing versus manual review before changing F019 routing.

## Inputs
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`

## Input Fields
- `original_test_result`
- `backtest_decision_state`
- `commercial_note`
- `watch_data_summary`
- `history_recommendation`
- `phase_recommendation`
- `recommendation`
- `failure_event_count`
- `longest_failure_streak_days`
- `time_normal_sell_days`
- `time_hold_wait_days`
- `time_selloff_days`
- `phase_profit_pct`
- `phase_low_roi_pct`
- `phase_break_even_pct`
- `phase_loss_pct`

## Planned Output
- Path: `out/analysis_reports/f_history_risk_pass_conflict_audit_latest.csv`

Required columns:
- `asin`
- `candidate_id`
- `supplier_sku`
- `review_pack_type`
- `history_risk_code`
- `history_recommended_action`
- `history_supporting_codes`
- `history_recommendation`
- `phase_recommendation`
- `backtest_recommendation`
- `commercial_label`
- `failure_event_count`
- `time_normal_sell_days`
- `time_selloff_days`
- `expected_units_next_30d`
- `expected_profit_next_30d_gbp`
- `evidence_source`

## Planned Rule Codes
- `history_fail_phase_avoid`
  - `history_recommendation=FAIL` and `phase_recommendation=AVOID`.
  - Recommended action: `remove_from_clean_pass`.
- `backtest_avoid_commercial_avoid_or_exit`
  - Backtest recommendation is Avoid or Exit-only, and commercial note starts Avoid or Exit-only.
  - Recommended action: `remove_from_clean_pass`.
- `exit_only_clean_pass`
  - Commercial or backtest label is Exit-only while row is clean Pass.
  - Recommended action: `remove_from_clean_pass`.
- `failure_events_100_plus`
  - Failure event count is at least 100.
  - Recommended action: `manual_review` unless a stronger remove rule is present.
- `selloff_days_exceed_normal_days`
  - Historical sell-off days exceed normal selling days.
  - Recommended action: `manual_review` unless a stronger remove rule is present.
- `history_risk_clear`
  - No direct history-risk conflict.
  - Recommended action: `allow_if_other_checks_pass`.

## Implementation Phases
- Phase 1: Audit only.
  - Create `scripts/one_off/F025_build_history_risk_pass_conflict_audit.py`.
  - Create `tests/test_f025_build_history_risk_pass_conflict_audit.py`.
  - Write output CSV only.
- Phase 2: Decision brief.
  - Produce human-readable counts and examples.
  - Confirm routing actions.
- Phase 3: F021 triage integration.
  - Add accepted history-risk evidence into triage output.
- Phase 4: F019 upstream routing.
  - Route accepted remove/manual-review rows out of clean Pass before pass pack write.

## Tests For Phase 1
- History FAIL plus phase AVOID creates `history_fail_phase_avoid`.
- Backtest Avoid plus commercial Avoid creates `backtest_avoid_commercial_avoid_or_exit`.
- Exit-only clean Pass creates `exit_only_clean_pass`.
- Failure event count over 100 creates `failure_events_100_plus`.
- Sell-off days greater than normal days creates `selloff_days_exceed_normal_days`.
- Clear rows produce `history_risk_clear`.
- Stronger remove-from-clean-pass rules outrank manual-review rules.
- Output has no unclassified rows.

## Do Not Do Yet
- Do not change F019 routing yet.
- Do not change F021 yet.
- Do not run scraper.
- Do not change Sheets or DB.

