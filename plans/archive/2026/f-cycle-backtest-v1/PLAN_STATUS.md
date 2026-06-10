# Plan Status

## Summary
- Plan slug: `f-cycle-backtest-v1`
- Current stage: Batch 008 active for operator alignment; Batch 009 defined as the next demand-basis cleanup batch
- Current batch: Batch 008 - guided sample review, historical refresh proof, and dual-mode validation
- Overall status: Active, implemented core v1, running Batch 008 review, with Batch 009 prepared as the next root-cause demand cleanup

## Checklist
- [x] Project brief written
- [x] Blueprint written
- [x] Data contracts written
- [x] Batch 001 complete
- [x] Batch 002 complete
- [x] Batch 003 complete
- [x] Batch 004 complete
- [x] Batch 005 complete
- [x] Batch 006 complete
- [x] Batch 007 complete
- [x] Batch 008 written
- [ ] Batch 008 complete
- [x] Batch 009 written
- [ ] Batch 009 complete
- [x] Runbook written
- [ ] Ready to archive

## Open blockers
- Operator expectation alignment across scenario samples has not been recorded yet.
- Monday raw F evidence has not yet been folded into a fresh backtest snapshot.
- Historical refresh path exists via `F003_refresh_backtest_after_policy_change.py`, but it is not yet proven as the official "change the rules and refresh past results" path.
- Explicit simple decision state for both historical backtest and future F scans is not yet locked.
- Replay demand still risks overstatement because BBP helper chosen units can override trusted monthly chart evidence until Batch 009 is implemented.
- There is no full sampled-ASIN BBP sales audit export yet, so operator verification still depends on one-by-one spot checks.
- Broader project-control docs still do not clearly track the backtest as an active delivered part of F/O planning.

## Latest proof snapshot
- Date: 2026-04-13
- Evidence:
  - latest global `out/system_health_checklist.csv` review showed no active `warn` or `fail` rows
  - raw F evidence now includes:
    - `f_screening_row_state_live.csv` rows = 35957
    - `feeder_legacy_scrape_evidence_live.csv` rows = 1243
    - `feeder_legacy_chart_daily_raw_live.csv` rows = 210888
  - latest raw F queue snapshot showed active supplier rows still pending, so raw-evidence growth is ahead of full queue completion
  - latest backtest outputs remain the 2026-04-11 snapshot:
  - `feeder_backtest_input_view_live.csv` rows = 355
  - `feeder_backtest_replay_daily_live.csv` rows = 108388
  - `feeder_backtest_summary_live.csv` rows = 355
  - `feeder_backtest_health.csv` rows = 12, all `ok`
  - `f_backtest_attribution_confidence_share` = `ok` (ready_rows=304, attribution_warn_rows=13)
  - `f_backtest_share_prior_dependency` = `ok` (prior_dependency_rows=365, replay_rows=108388)
  - `f_backtest_sales_share_validity` = `ok`
  - `f_backtest_calibration_set_latest.csv` rows = 18

## Notes
- Source planning and execution docs were copied from `reference/Backtest Strategy Ideas/` into this active plan folder on 2026-04-11.
- Original reference files remain the research/archive source.
- This folder is now the durable starting point for future F backtest sessions.
- Batch 005 moved replay share logic from provisional fixed defaults to measured scenario rates with prior fallback.
- Batch 006 added attribution-confidence reason tags and confidence downgrades with a scoped attribution health check.
- Batch 007 added governed scenario share caps, replay share-source tags, summary share-basis update, and prior-dependency health visibility.
- Batch 008 is now the agreed continuation point for user-sample alignment, historical refresh proof, and `screening` vs `data_collection` validation.
- Batch 009 was defined on 2026-04-13 after user review exposed that BBP monthly sales replay can be inflated by future bars, partial-month bars, or helper chosen demand leaking into replay basis.
- Batch 009 now also requires a full sampled-ASIN audit export so the operator can compare every reviewed ASIN against scraped BBP month history and replay demand basis in one list.
