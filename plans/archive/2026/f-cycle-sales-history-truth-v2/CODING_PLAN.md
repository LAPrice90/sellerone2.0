# F Sales History Truth V2 - Coding Plan

Date: 2026-04-20
Scope: turn the active F plan into a durable phase-by-phase execution sequence so implementation, runtime proof, and next steps do not live only in chat.

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 1 | Lock demand-truth contracts and validation baseline | F071 to F074, one-off audit helpers, tests, plan files | F-scoped pytest pack | no | complete |
| Phase 2A | Build live validation and targeted subset tooling | F006 to F009, runner files, tests, plan files | F-scoped pytest pack | no | complete |
| Phase 2B | Run the live subset recovery and rebuild outputs | approved one-off F runner path, rebuild owners, plan files | one-off run proof plus scoped checks | yes | complete (bounded live proof window) |
| Phase 3 | Harden price-qualified demand engine | owned F logic and tests only | targeted F pack | yes | complete (controlled proof window, 2026-04-19) |
| Phase 4 | Add seasonality, stability, and recent-performance classifier | owned F logic and tests only | targeted F pack | yes | complete (controlled proof window, 2026-04-20) |
| Phase 5 | Final decision summary and confidence engine | owned F logic and tests only | targeted F pack | yes | complete (controlled proof window, 2026-04-20) |
| Phase 6 | Accuracy and operator validation pack | one-off validation owners and tests | targeted F pack | yes | complete (controlled proof window, 2026-04-20) |
| Phase 7 | Post-purchase 90-day learning loop | planned F owner path and tests | targeted F pack | yes | complete (controlled one-off proof window, 2026-04-20) |

## 1A) Working baseline frozen on 2026-04-20

- Raw scrape evidence available for model work:
  - scrape-evidence rows: `4580`
  - unique ASINs seen: `4556`
  - latest successful ASIN captures: `2342`
- Latest-success month coverage:
  - `6+` observed months: `1918`
  - `9+` observed months: `1528`
  - `12+` observed months: `1012`
- Fresh targeted retry subset built for cleanup only:
  - report:
    - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`
  - selected rows:
    - `2207`
- Refreshed model-layer rebuild against the frozen dataset:
  - `F071`: `2358` rows (`ready=2149`, `manual_review=209`)
  - `F072`: `769366` rows
  - `F073`: `2358` rows (`fail=1883`, `manual_review=209`, `pass=266`)
  - `F074`: `17` rows (`ok=17`)
  - `F004`: `18` rows (`mismatch_rows=2`)
  - `F005`: `28668` rows (`trusted_rows=2262`, `qualified_delta_rows=28418`)
- Operating decision from this baseline:
  - do not continue broad scrape collection for this ticket
  - Phase 7 learning-loop implementation is complete on the frozen dataset outputs
  - continue with archive-readiness review and next-plan split only if required
  - keep retry work as a separate one-off recovery lane

## 2) Phase details

### Phase 2A - Tooling and capture path
Goal:
- complete the tooling needed before the live subset recovery window

Files allowed to change:
- `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
- `scripts/one_off/F008_capture_full_bbp_evidence_pack.py`
- `scripts/one_off/F009_build_full_capture_consistency_audit.py`
- `run_F_shure_full_legacy_scan.bat`
- `run_F_shure_test_mode_scan_once.bat`
- `run_F_supplier_full_legacy_scan.bat`
- `run_F_supplier_test_mode_scan_once.bat`
- related tests
- plan files

Implementation tasks completed:
- added targeted subset builder for missing completed-month basis rows
- added live Chrome full-capture helper and consistency audit
- aligned runner files with `stocklist_supplier`

Isolated verification:
- command:
  - `pytest tests/test_f004_build_bbp_sales_sample_audit.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f006_build_live_asin_validation_pack.py tests/test_f007_prepare_targeted_rescrape_subset.py tests/test_f061_run_legacy_first_checks_local.py tests/test_f071_build_backtest_input_view.py tests/test_f074_build_backtest_health.py`
  - `pytest tests/test_f008_capture_full_bbp_evidence_pack.py tests/test_f009_build_full_capture_consistency_audit.py`
- expected result:
  - pass

Monitored validation:
- live proof needed:
  - no

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: not required

### Phase 2B - Live subset recovery and rebuild proof
Goal:
- run the actual subset recovery window, rebuild owned F outputs, and decide whether the plan can move to Phase 3

Files allowed to change:
- plan files only unless the live proof exposes a root-cause contract gap

Implementation tasks:
- run the approved targeted subset path on the live supplier queue
- rebuild `F070` to `F074`
- rebuild `F004` and `F005`
- capture before/after coverage and decision-state deltas

Isolated verification:
- command:
  - use existing passed Phase 2A tooling and runner proof as the isolated base
- expected result:
  - tooling already proven; this phase depends on live one-off proof

Monitored validation:
- live proof needed:
  - yes
- proof window executed:
  - start snapshot:
    - `2026-04-18T20:33:29Z`
  - completion snapshot:
    - `2026-04-18T21:20:26Z`
- proof checkpoints completed:
  - mixed live-ASIN pack built:
    - `12` rows (`trusted_completed_month=4`, `explicit_zero_history=2`, `missing_completed_month_basis=6`)
  - targeted subset applied:
    - supplier queue `32872 -> 2248`
  - targeted subset run completed:
    - `F061` data-collection window processed `25` subset rows
  - rebuild outputs completed:
    - `F070` to `F074`, `F004`, `F005`
  - full queue restored and overnight ownership confirmed:
    - supplier queue restored to `42663`
    - loop owner resumed with `run_F_supplier_full_legacy_scan.bat stocklist_supplier`
- coverage remeasurement:
  - prompt baseline (stale but required reference):
    - evidence rows: `1581`
    - completed-month rows: `330`
    - missing full-chart rows with ASIN: `1251`
  - live window baseline:
    - evidence rows: `4598`
    - completed-month rows: `2241`
    - missing full-chart rows with ASIN: `2244`
  - after bounded proof run:
    - evidence rows: `4598`
    - completed-month rows: `2264` (`+23`)
    - missing full-chart rows with ASIN: `2219` (`-25`)
- timeout rule:
  - if coverage or ownership proof regresses, park as `pending next live subset proof window` with exact missing artifact and resume trigger
- next automatic step after success:
  - do not start Phase 3 until a fresh phase gate decision confirms coverage is sufficient for broader hardening
- notification mode:
  - passive
- user interruption threshold:
  - phase complete
  - new or worse alert
  - contradictory evidence
  - timeout that blocks automatic continuation
  - approval-required live action

Phase status:
- code fix applied: yes for the tooling that enables this phase
- isolated verification passed: yes for the enabling tooling
- monitored validation: live subset recovery proof completed (bounded window, 2026-04-18)

### Phase 3 - Harden price-qualified demand engine
Goal:
- make price qualification explicit, auditable, and source-aligned before any seasonality or recent-performance work begins

Files allowed to change:
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/_source_contracts.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- related tests
- plan files

Implementation tasks:
- expose qualification components explicitly in the earliest F owner stage
- keep raw demand and qualified demand separate end to end
- ensure READY rows use qualified-demand source truth consistently in replay and summary
- extend F health and validation proof so qualification reason paths can be checked directly

Isolated verification:
- command:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
  - `python -m py_compile <changed F files and tests>`
- expected result:
  - qualification components are explicit
  - source alignment holds on READY rows
  - health and validation output cover the new contract

Monitored validation:
- live proof needed:
  - yes
- artifacts to poll:
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- proof boundary:
  - use a controlled F proof window so live-owner movement does not create false stale-proof ambiguity
- success threshold:
  - qualification component fields are present and non-blank on READY rows
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - validation audit exposes raw vs qualified delta and reason path
  - proof should target `f_backtest_health_staleness = ok` on the controlled window
- timeout rule:
  - park as `pending controlled F proof window` with the exact stale source, ownership blocker, or missing output
- next automatic step after success:
  - create or refresh Batch 004 package only after Phase 3 proof is written into the plan docs
- notification mode:
  - passive
- user interruption threshold:
  - phase complete
  - new or worse alert
  - contradictory evidence
  - blocked proof boundary
  - approval-required live action
- proof window executed:
  - owner pause was applied before first rebuild artifact write
  - first rebuild artifact timestamp:
    - `2026-04-19T07:02:18Z` (`F070`)
  - rebuild completion:
    - `2026-04-19T07:23:07Z` (`F005`)
    - `2026-04-19T07:24:34Z` final `F074` rerun for staleness close
- controlled-boundary truth:
  - `feeder_legacy_scrape_evidence_live.csv` hash unchanged across proof:
    - `E38EE98FC4EA278CF41F4CCEAED7C6C737FA8D1DFB2ACA2CB20CCD429EA3E481`
- rebuild evidence:
  - `F071` rows: `2364` (`ready=2158`, `manual_review=206`)
  - `F072` rows: `772366`
  - `F073` rows: `2364` (`ready=2158`, `manual_review=206`)
  - `F074` rows: `17` (`ok=17`, `warn=0`, `fail=0`)
  - `F004` rows: `18`, mismatch rows: `2`
  - `F005` rows: `28764`, trusted rows: `2270`, qualified-delta rows: `28540`
- health proof:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - `f_backtest_qualification_source_alignment = ok`
  - `f_backtest_health_staleness = ok`
- source alignment proof:
  - READY summary rows: `2158`
  - READY expected units source `input_qualified`: `2158`
  - READY expected profit source `input_qualified`: `2158`
  - READY rows with blank qualification components: `0`
- owner restoration proof:
  - canonical queue rows for `stocklist_supplier`: `42663`
  - loop owner restored:
    - `python ... F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 5 --loop`

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - controlled Phase 3 proof completed (bounded freeze, 2026-04-19)

### Phase 4 - Seasonality, stability, and recent-performance classifier
Goal:
- add explicit classifier truth for seasonality, stability/drift, and recent vs baseline before confidence-model work

Files allowed to change:
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/_source_contracts.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- related tests
- plan files

Implementation tasks:
- add maturity-aware seasonality states with explicit reason path
- add stability/drift states from qualified demand history
- add recent-vs-baseline states and reason tags from qualified demand context
- propagate classifier truth through replay and summary without hidden optimistic fallback
- extend F health and validation proof for classifier integrity

Isolated verification:
- command:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
  - `python -m py_compile <changed F files and tests>`
- expected result:
  - classifier fields and reason tags are explicit
  - READY rows carry non-blank classifier state path
  - F health shows classifier-integrity checks as `ok`

Monitored validation:
- live proof needed:
  - yes
 - default proof boundary for this phase:
   - use the frozen `2026-04-20` dataset and refreshed rebuild outputs as the starting point
   - do not restart a broad scrape loop as part of Phase 4 proof
- artifacts to poll:
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- proof boundary:
  - controlled F proof window with fixed scrape evidence boundary
- success threshold:
  - seasonality/stability/recent fields present on READY rows
  - classifier source/reason path non-blank where required
  - classifier health checks `ok`
  - `f_backtest_health_staleness = ok`
- timeout rule:
  - park as `pending controlled F proof window` with exact blocker and exact resume trigger
- next automatic step after success:
  - prepare Batch 005 package; do not implement confidence engine until Phase 4 proof is logged
- notification mode:
  - passive
- user interruption threshold:
  - phase complete
  - new or worse alert
  - contradictory evidence
  - blocked proof boundary
  - approval-required live action

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - controlled Phase 4 proof completed (bounded freeze, 2026-04-20)
  - proof window runs:
    - `F071` at `2026-04-20T13:10:00Z` -> rows `2358` (`ready=2149`, `manual_review=209`)
    - `F072` at `2026-04-20T13:11:00Z` -> rows `769366`
    - `F073` at `2026-04-20T13:12:00Z` -> rows `2358` (`ready=2149`, `manual_review=209`)
    - `F074` first pass at `2026-04-20T13:13:00Z` -> `ok=19`, `warn=1` (`staleness`)
    - `F074` closeout pass at `2026-04-20T13:15:00Z` -> `ok=20`, `warn=0`, `fail=0`
    - `F005` at `2026-04-20T13:14:00Z` -> rows `28668`, trusted rows `2262`, qualified-delta rows `28418`
  - classifier integrity truth on closeout pass:
    - `f_backtest_seasonality_classifier_integrity = ok`
    - `f_backtest_stability_classifier_integrity = ok`
    - `f_backtest_recent_vs_baseline_integrity = ok`
    - READY summary rows `2149`, blank classifier-state rows `0`, blank classifier-reason rows `0`

### Phase 5 - Final decision summary and confidence engine
Goal:
- make decision confidence explicit and enforceable in summary, health, and validation outputs

Files allowed to change:
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- related tests
- plan files

Implementation tasks:
- add explicit `decision_confidence` and `decision_confidence_reason_codes` to summary output
- route low-confidence ready rows to `manual_review` while preserving floor-based fail behavior
- add F-scoped confidence integrity check in health
- extend one-off validation export with confidence fields for operator sampling

Isolated verification:
- command:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
  - `python -m py_compile <changed F files and tests>`
- result:
  - `49 passed`
  - `py_compile` passed for all changed files

Monitored validation:
- live proof needed:
  - yes
- default proof boundary for this phase:
  - controlled rebuild on frozen evidence with closeout health rerun
- artifacts polled:
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- success threshold:
  - READY summary rows have non-blank confidence fields
  - no READY `pass` row with `decision_confidence=low`
  - `f_backtest_decision_confidence_integrity = ok`
  - `f_backtest_decision_floor_integrity = ok`
  - `f_backtest_health_staleness = ok` on closeout
- proof window runs:
  - `F070` at `2026-04-20T15:20:00Z` -> rows `1` (`active_rows=1`)
  - `F071` at `2026-04-20T15:21:00Z` -> rows `2358` (`ready=2149`, `manual_review=209`)
  - `F072` at `2026-04-20T15:22:00Z` -> rows `769366`
  - `F073` at `2026-04-20T15:23:00Z` -> rows `2358` (`ready=2149`, `manual_review=209`)
  - `F074` first pass at `2026-04-20T15:24:00Z` -> `ok=20`, `warn=1` (`staleness`)
  - `F074` closeout pass at `2026-04-20T15:25:00Z` -> `ok=21`, `warn=0`, `fail=0`
  - `F005` at `2026-04-20T15:26:00Z` -> rows `28668`, trusted rows `2262`, qualified-delta rows `28418`
- closeout truth:
  - `f_backtest_decision_floor_integrity = ok`
  - `f_backtest_decision_confidence_integrity = ok`
  - READY summary rows `2149`, blank confidence rows `0`, blank confidence-reason rows `0`
  - READY `pass` rows with low confidence `0`
  - confidence distribution:
    - `medium=1251`
    - `low=1107`
  - decision distribution:
    - `fail=1883`
    - `pass=266`
    - `manual_review=209`
  - validation export confidence coverage:
    - rows with `decision_confidence`: `28541`
    - rows with `decision_confidence_reason_codes`: `28541`
- timeout rule:
  - if closeout health cannot reach `ok`, park as `pending controlled F closeout rerun` with exact blocking check
- next automatic step after success:
  - prepare Batch 006 execution package

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - controlled Phase 5 proof completed (bounded freeze, 2026-04-20)

### Phase 6 - Accuracy and operator validation pack
Goal:
- build a repeatable one-off accuracy pack that compares model output with operator checks and reports error buckets

Files allowed to change:
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- related tests
- plan files

Implementation tasks:
- define operator-check input contract for sampled ASIN validation
- join calibration sample, latest summary, and operator checks into one row-level accuracy pack
- emit explicit decision and units mismatch buckets plus missing-input buckets
- emit summary counts and operator template for next review cycle

Isolated verification:
- command:
  - `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f002_build_backtest_calibration_set.py`
  - `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py tests/test_f011_build_sales_history_accuracy_pack.py`
- result:
  - `10 passed`
  - `py_compile` passed for changed script and test

Monitored validation:
- live proof needed:
  - yes
- default proof boundary for this phase:
  - one-off runtime proof against latest sampled calibration set and summary
- artifacts produced:
  - `out/analysis_reports/f_sales_history_accuracy_pack_latest.csv`
  - `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
  - `out/analysis_reports/f_operator_sales_checks_template_latest.csv`
- proof run:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py --observed-utc 2026-04-20T12:53:00Z`
- closeout truth:
  - accuracy pack rows: `18`
  - mismatch rows: `0`
  - needs operator input rows: `18`
  - summary bucket counts:
    - `missing_operator_check=18`
    - `missing_operator_units=18`
    - `missing_operator_decision=18`
- timeout rule:
  - if script fails to emit latest files, park as `pending one-off accuracy rebuild` with exact missing file
- next automatic step after success:
  - start Batch 007 implementation using `EXECUTION_BATCH_007.md`

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - controlled Phase 6 one-off proof completed (2026-04-20)

### Phase 7 - Post-purchase 90-day learning loop
Goal:
- capture buy-time assumptions and compare them against 90-day outcomes using one-off, file-based workflow

Files allowed to change:
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_007.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- related tests under `tests/`

Implementation tasks:
- define one-off input contract for:
  - decision snapshot rows from `feeder_backtest_summary_live.csv`
  - operator or outcome check rows for 30d/60d/90d outcome comparison
- build append-safe learning log output:
  - `out/systems/F/live/feeder_sales_history_learning_live.csv`
- emit one-off review outputs for operator sign-off:
  - `out/analysis_reports/f_sales_history_learning_review_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_health_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv`
- classify outcome truth with explicit reason codes:
  - `right_call`
  - `demand_too_high`
  - `demand_too_low`
  - `price_assumption_wrong`
  - `amazon_suppressed`
  - `seasonality_misread`
  - `operational_blocker`

Isolated verification:
- command:
  - `pytest tests/test_f012_build_sales_history_learning_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py`
  - `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py tests/test_f012_build_sales_history_learning_pack.py`
- expected result:
  - input parsing, dedupe keys, learning outcome classification, and output schemas are covered

Monitored validation:
- live proof needed:
  - yes
- default proof boundary for this phase:
  - one-off controlled run only (no daily-loop promotion)
- artifacts to poll:
  - `out/systems/F/live/feeder_sales_history_learning_live.csv`
  - `out/analysis_reports/f_sales_history_learning_review_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_health_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv`
- success threshold:
  - output files exist and latest pointers refresh in same run
  - `learning_outcome` only uses the controlled value set
  - no duplicate key rows for the same decision snapshot identity
  - learning health report shows explicit row counts and missing-outcome counts
- proof run:
  - `python scripts/one_off/F012_build_sales_history_learning_pack.py --observed-utc 2026-04-20T13:02:00Z`
- closeout truth:
  - `feeder_sales_history_learning_live.csv`: rows `266`
  - `f_sales_history_learning_review_latest.csv`: rows `266`
  - `f_sales_history_learning_health_latest.csv`: rows `14`
  - `f_sales_history_learning_actuals_template_latest.csv`: rows `266`
  - pending outcomes: `266`
  - controlled outcome set respected
- timeout rule:
  - park as `pending one-off learning proof` with exact missing file or missing schema field
- next automatic step after success:
  - prepare archive-readiness review for this plan and split remaining work into next active plan only if needed
- notification mode:
  - passive
- user interruption threshold:
  - phase complete
  - new or worse alert
  - contradictory evidence
  - blocked proof boundary
  - approval-required scope change

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - controlled Phase 7 one-off proof completed (2026-04-20)

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
